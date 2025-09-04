# ova_to_ami.py
# A script to automate the process of converting an OVA file to an AWS AMI.
# This script creates a dedicated IAM role for the VM Import/Export service.

import boto3
import os
import json
import time
import sys
import argparse
import uuid

# --- Configuration ---
# IAM role and policy names are hardcoded as they are standard for this process.
IAM_ROLE_NAME = "vmimport"
IAM_POLICY_NAME = "vmimport"

# --- Helper Functions ---

def create_s3_bucket(s3_client, bucket_name):
    """
    Creates a new S3 bucket with a unique name.
    """
    print(f"Attempting to create S3 bucket: {bucket_name}")
    try:
        # Get the current region from the Boto3 session
        current_region = s3_client.meta.region_name
        
        if current_region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': current_region}
            )
        print(f"Successfully created S3 bucket: {bucket_name}")
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"Bucket '{bucket_name}' already exists and is owned by you. Proceeding...")
    except Exception as e:
        print(f"Error creating S3 bucket: {e}", file=sys.stderr)
        sys.exit(1)

def create_iam_role_and_policy(iam_client, s3_bucket):
    """
    Creates the necessary IAM role and policy for VM Import/Export.
    Checks if the role already exists to avoid errors.
    """
    print("Checking for existing IAM role...")
    try:
        iam_client.get_role(RoleName=IAM_ROLE_NAME)
        print(f"IAM role '{IAM_ROLE_NAME}' already exists. Skipping creation.")
    except iam_client.exceptions.NoSuchEntityException:
        print(f"IAM role '{IAM_ROLE_NAME}' not found. Creating...")
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "vmie.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "sts:ExternalId": "vmimport"
                        }
                    }
                }
            ]
        }
        
        try:
            iam_client.create_role(
                RoleName=IAM_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            print("IAM role created successfully.")
            
            # Create and attach the role policy
            role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{s3_bucket}",
                            f"arn:aws:s3:::{s3_bucket}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:ModifySnapshotAttribute",
                            "ec2:CopySnapshot",
                            "ec2:RegisterImage",
                            "ec2:Describe*"
                        ],
                        "Resource": "*"
                    }
                ]
            }
            
            iam_client.put_role_policy(
                RoleName=IAM_ROLE_NAME,
                PolicyName=IAM_POLICY_NAME,
                PolicyDocument=json.dumps(role_policy)
            )
            print("IAM role policy attached successfully.")
            
            # Wait for the role to become available
            print("Waiting for IAM role to propagate...")
            waiter = iam_client.get_waiter('role_exists')
            waiter.wait(RoleName=IAM_ROLE_NAME)
            print("IAM role is now available.")
            
        except Exception as e:
            print(f"Error creating IAM role or policy: {e}", file=sys.stderr)
            sys.exit(1)

def upload_ova_to_s3(s3_client, bucket_name, file_path):
    """Uploads the OVA file to the specified S3 bucket."""
    file_name = os.path.basename(file_path)
    print(f"Uploading '{file_name}' to S3 bucket '{bucket_name}'...")
    
    try:
        s3_client.upload_file(file_path, bucket_name, file_name)
        print(f"Successfully uploaded '{file_name}' to S3.")
        return file_name
    except Exception as e:
        print(f"Error uploading file to S3: {e}", file=sys.stderr)
        sys.exit(1)

def import_image(ec2_client, s3_bucket, ova_key, description):
    """Initiates the VM import task."""
    print("Initiating VM import task...")
    
    disk_container = {
        "Description": description,
        "Format": "ova",
        "UserBucket": {
            "S3Bucket": s3_bucket,
            "S3Key": ova_key
        }
    }
    
    try:
        response = ec2_client.import_image(
            Description=description,
            DiskContainers=[disk_container]
        )
        import_task_id = response['ImportTaskId']
        print(f"Import task started. Task ID: {import_task_id}")
        return import_task_id
    except Exception as e:
        print(f"Error initiating import task: {e}", file=sys.stderr)
        sys.exit(1)

def monitor_import_task(ec2_client, task_id):
    """Polls the import task status until it's complete."""
    print("Monitoring import task status...")
    while True:
        try:
            response = ec2_client.describe_import_image_tasks(
                ImportTaskIds=[task_id]
            )
            task = response['ImportImageTasks'][0]
            status = task['Status']
            status_message = task.get('StatusMessage', 'No message')
            
            print(f"Current status: {status} - {status_message}")
            
            if status in ['completed', 'deleted', 'cancelled']:
                return task
            
            # Wait for 30 seconds before polling again
            time.sleep(30)
            
        except Exception as e:
            print(f"Error monitoring import task: {e}", file=sys.stderr)
            sys.exit(1)

def main():
    """Main function to run the entire automation workflow."""
    parser = argparse.ArgumentParser(description="Automate OVA to AMI conversion using Boto3.")
    parser.add_argument("--input", required=True, help="Path to the .ova file to import.")
    args = parser.parse_args()
    
    ova_file_path = args.input
    
    print("Starting OVA to AMI conversion script...")
    
    if not os.path.exists(ova_file_path):
        print(f"Error: OVA file not found at '{ova_file_path}'", file=sys.stderr)
        sys.exit(1)
    
    # Initialize AWS clients
    try:
        iam_client = boto3.client('iam')
        ec2_client = boto3.client('ec2')
        s3_client = boto3.client('s3')
    except Exception as e:
        print(f"Error initializing AWS clients. Ensure Boto3 is installed and your AWS credentials are configured. Details: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Generate a unique bucket name
    bucket_name = f"ova-ami-import-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    ami_description = f"AMI created from {os.path.basename(ova_file_path)}"

    # 1. Create S3 bucket
    create_s3_bucket(s3_client, bucket_name)
    
    # 2. Create IAM role and policy
    create_iam_role_and_policy(iam_client, bucket_name)
    
    # 3. Upload OVA file to S3
    ova_s3_key = upload_ova_to_s3(s3_client, bucket_name, ova_file_path)
    
    # 4. Start import task
    import_task_id = import_image(ec2_client, bucket_name, ova_s3_key, ami_description)
    
    # 5. Monitor and wait for completion
    final_task_status = monitor_import_task(ec2_client, import_task_id)
    
    if final_task_status['Status'] == 'completed':
        ami_id = final_task_status['ImageId']
        print("\n--- Conversion Complete ---")
        print(f"The OVA file has been successfully converted to an AMI.")
        print(f"Final AMI Location (ID): {ami_id}")
    else:
        print("\n--- Conversion Failed ---")
        print("The import task did not complete successfully.")
        print(f"Final Status: {final_task_status['Status']}")
        print(f"Status Message: {final_task_status.get('StatusMessage', 'N/A')}")

if __name__ == "__main__":
    main()
