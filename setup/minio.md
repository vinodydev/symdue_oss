docker exec a9fbf82510b3 /bin/sh -c "pip3 install boto3 && python3 -c '
import boto3
import json

# --- CONFIGURATION ---
MINIO_URL = \"http://minio:9000\"  # Ensure this hostname is reachable from INSIDE this container
ACCESS_KEY = \"minioadmin\"
SECRET_KEY = \"minioadmin\"
BUCKET_NAME = \"graphmind-files\"

def make_bucket_public():
    try:
        s3 = boto3.client(\"s3\",
            endpoint_url=MINIO_URL,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
        )

        public_policy = {
            \"Version\": \"2012-10-17\",
            \"Statement\": [
                {
                    \"Sid\": \"PublicRead\",
                    \"Effect\": \"Allow\",
                    \"Principal\": \"*\",
                    \"Action\": [\"s3:GetObject\"],
                    \"Resource\": [f\"arn:aws:s3:::{BUCKET_NAME}/*\"]
                }
            ]
        }

        s3.put_bucket_policy(
            Bucket=BUCKET_NAME,
            Policy=json.dumps(public_policy)
        )
        print(f\"SUCCESS: Bucket {BUCKET_NAME} is now PUBLIC.\")
    except Exception as e:
        print(f\"Error: {e}\")

if __name__ == \"__main__\":
    make_bucket_public()
'"