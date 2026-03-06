CourseStack OVA to AMI Converter
================================

This tool automates the ingestion of virtual machine images into the **CourseStack** ecosystem. It handles the heavy lifting of AWS infrastructure preparation, S3 uploading with real-time progress tracking, and the conversion of `.ova` files into shared Amazon Machine Images (AMIs).

Overview
-----------

The script performs the following sequence of operations:

1.  **Infrastructure Setup**: Creates a temporary S3 bucket and configures the necessary `vmimport` IAM roles and policies.

2.  **High-Speed Upload**: Uploads your OVA file to S3 with a real-time progress bar.

3.  **AWS Conversion**: Initiates the `import-image` process and monitors progress until completion.

4.  **Automated Sharing**: Automatically shares the resulting AMI and its underlying EBS storage with the CourseStack production account (`662863940582`).

5.  **Cleanup**: Deletes the temporary S3 bucket and OVA file to minimize costs.

🛠 Prerequisites
----------------

-   **Python 3.6+**

-   **AWS CLI** configured with permissions to manage IAM, S3, and EC2.

-   **Required Libraries**:

    Bash

    ```
    pip install boto3 tqdm

    ```

Usage
--------

Clone this repository and run the script pointing to your local `.ova` file:

Bash

```
python ova_to_ami.py --input /path/to/your/image.ova

```

### Example Output

Plaintext

```
[*] Creating temporary S3 bucket: ovastack-import-1709734315
[*] Configuring IAM roles and permissions...
[*] Uploading my-lab-vm.ova to S3...
my-lab-vm.ova: 100%|██████████████████████| 2.45G/2.45G [01:12<00:00, 34.1MB/s]
[*] Initiating AMI Import...
[*] AWS is now converting the OVA to an AMI (Task: import-ami-08e1a...)
    -> Current AWS Status: active (25%) - converting
    -> Current AWS Status: completed (100%) - success
[*] Sharing AMI and Storage with Account 662863940582...
[*] Cleaning up temporary S3 bucket...

Import is complete. The AMI ID for CourseStack is ami-0a1b2c3d4e5f6g7h8

```

Configuration
----------------

The script is pre-configured to share resources with the primary CourseStack account. If you need to modify the target account, update the `TARGET_ACCOUNT_ID` constant at the top of the script:


Important Note
------------------
-   **IAM Permissions**: The script attempts to create the `vmimport` role. If your AWS user does not have IAM administrative privileges, ask your administrator to run the script once to initialize the environment.
