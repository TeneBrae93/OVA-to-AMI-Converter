import boto3
import os
import json
import time
import sys
import argparse
import uuid
from tqdm import tqdm

# --- Configuration ---
IAM_ROLE_NAME = "vmimport"
IAM_POLICY_NAME = "vmimport"
TARGET_ACCOUNT_ID = "662863940582"

def create_s3_bucket(s3_client, bucket_name):
    print(f"[*] Creating temporary S3 bucket: {bucket_name}")
    try:
        current_region = s3_client.meta.region_name
        if current_region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': current_region}
            )
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        pass

def create_iam_role_and_policy(iam_client, s3_bucket):
    print("[*] Configuring IAM roles and permissions...")
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "vmie.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"sts:ExternalId": "vmimport"}}
        }]
    }
    try:
        iam_client.get_role(RoleName=IAM_ROLE_NAME)
    except iam_client.exceptions.NoSuchEntityException:
        iam_client.create_role(RoleName=IAM_ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust_policy))

    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{s3_bucket}", f"arn:aws:s3:::{s3_bucket}/*"]
            },
            {
                "Effect": "Allow",
                "Action": ["ec2:ModifySnapshotAttribute", "ec2:CopySnapshot", "ec2:RegisterImage", "ec2:Describe*"],
                "Resource": "*"
            }
        ]
    }
    iam_client.put_role_policy(RoleName=IAM_ROLE_NAME, PolicyName=IAM_POLICY_NAME, PolicyDocument=json.dumps(role_policy))
    time.sleep(5) 

def upload_with_progress(s3_client, bucket_name, file_path):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    print(f"[*] Uploading {file_name} to S3...")
    with tqdm(total=file_size, unit='B', unit_scale=True, desc=file_name) as pbar:
        s3_client.upload_file(
            file_path, 
            bucket_name, 
            file_name,
            Callback=lambda bytes_transferred: pbar.update(bytes_transferred)
        )
    return file_name

def monitor_import_task(ec2_client, task_id):
    print(f"[*] AWS is now converting the OVA to an AMI (Task: {task_id})")
    print("[*] This process usually takes 15-45 minutes depending on image size.")
    
    # Using a simple spinner-style update for the long-running AWS task
    last_status = None
    while True:
        response = ec2_client.describe_import_image_tasks(ImportTaskIds=[task_id])
        task = response['ImportImageTasks'][0]
        status = task['Status']
        progress = task.get('Progress', '0')
        status_msg = task.get('StatusMessage', 'Processing')

        if status != last_status:
            print(f"    -> Current AWS Status: {status} ({progress}%) - {status_msg}")
            last_status = status

        if status in ['completed', 'deleted', 'cancelled']:
            return task
        time.sleep(30)

def share_resources(ec2_client, ami_id, target_account):
    print(f"[*] Sharing AMI and Storage with Account {target_account}...")
    ec2_client.modify_image_attribute(
        ImageId=ami_id,
        LaunchPermission={'Add': [{'UserId': target_account}]}
    )
    
    image_info = ec2_client.describe_images(ImageIds=[ami_id])['Images'][0]
    for device in image_info.get('BlockDeviceMappings', []):
        if 'Ebs' in device:
            ec2_client.modify_snapshot_attribute(
                SnapshotId=device['Ebs']['SnapshotId'],
                Attribute='createVolumePermission',
                OperationType='add',
                UserIds=[target_account]
            )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File {args.input} not found.")
        sys.exit(1)

    s3_client = boto3.client('s3')
    iam_client = boto3.client('iam')
    ec2_client = boto3.client('ec2')
        
    bucket_name = f"ovastack-import-{int(time.time())}"
    
    # Execution steps
    create_s3_bucket(s3_client, bucket_name)
    create_iam_role_and_policy(iam_client, bucket_name)
    
    ova_key = upload_with_progress(s3_client, bucket_name, args.input)
    
    print("[*] Initiating AMI Import...")
    disk_container = {"Description": "CourseStack OVA", "Format": "ova", "UserBucket": {"S3Bucket": bucket_name, "S3Key": ova_key}}
    response = ec2_client.import_image(Description="CourseStack Image", DiskContainers=[disk_container])
    task_id = response['ImportTaskId']
    
    final_status = monitor_import_task(ec2_client, task_id)
    
    if final_status['Status'] == 'completed':
        ami_id = final_status['ImageId']
        share_resources(ec2_client, ami_id, TARGET_ACCOUNT_ID)
        
        # Cleanup
        print(f"[*] Cleaning up temporary S3 bucket...")
        s3_client.delete_object(Bucket=bucket_name, Key=ova_key)
        s3_client.delete_bucket(Bucket=bucket_name)
        
        print(f"\nImport is complete. The AMI ID for CourseStack is {ami_id}")
    else:
        print(f"\n[!] Import failed: {final_status.get('StatusMessage')}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()