# OVA to AWS AMI Conversion Script
This Python script automates the process of converting an on-premises virtual machine image in .ova format into an Amazon Machine Image (AMI) on AWS. It handles all the necessary steps, including creating a temporary S3 bucket, setting up the required IAM role, uploading the OVA file, and monitoring the conversion process until completion.

## How It Works
The script performs the following automated steps:
1. S3 Bucket Creation: A uniquely named S3 bucket is created in your AWS account's default region to temporarily store the .ova file.
2. IAM Role Setup: It checks for the existence of the required vmimport IAM service role. If the role does not exist, it automatically creates it with the necessary trust and resource policies to allow the VM Import/Export service to perform the conversion on your behalf.
3. File Upload: Your local .ova file is securely uploaded to the newly created S3 bucket.
4. Import Task Initiation: The script initiates the ImportImage task with Amazon EC2, referencing the uploaded file.
5. Status Monitoring: It continuously polls the status of the import task and prints the progress to the console.
6. AMI ID Output: Once the conversion is completed, the script outputs the final AMI ID, which you can use to launch new EC2 instances.

## Prerequisites
Before running this script, ensure you have the following:
- Python 3: The script requires Python 3.
- Boto3: The AWS SDK for Python. You can install it using pip.
- AWS Credentials: Your AWS CLI must be configured with a default profile that has administrator permissions. This includes permissions to create S3 buckets, manage IAM roles and policies, and interact with the EC2 service.
### Installation
If you don't have Boto3 installed, run the following command:

```python3 -m pip install boto3```

### Usage
To run the script, use the following command from your terminal, providing the path to your .ova file using the --input argument:

```python3 ova_to_ami.py --input /path/to/your/file.ova```




### Example
```
tyler@tyler:~/infrastructure$ python3 ova_to_ami.py --input BuildingMagic-1.2.ova
Starting OVA to AMI conversion script...
Attempting to create S3 bucket: ova-ami-import-1756932359-81ddd9a1
Successfully created S3 bucket: ova-ami-import-1756932359-81ddd9a1
Checking for existing IAM role...
IAM role 'vmimport' not found. Creating...
IAM role created successfully.
IAM role policy attached successfully.
Waiting for IAM role to propagate...
IAM role is now available.
Uploading 'BuildingMagic-1.2.ova' to S3 bucket 'ova-ami-import-1756932359-81ddd9a1'...
Successfully uploaded 'BuildingMagic-1.2.ova' to S3.
Initiating VM import task...
Import task started. Task ID: import-ami-02a8b9f1d0a52b6d7
Monitoring import task status...
Current status: active - Converting
...
Current status: active - Completed
--- Conversion Complete ---
The OVA file has been successfully converted to an AMI.
Final AMI Location (ID): ami-02a8b9f1d0a52b6d7```
