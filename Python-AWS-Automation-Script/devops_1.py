import boto3
import webbrowser
import time
import random
import string
import json
import requests
import os
import subprocess
import argparse

#Initializing the argument parser
parser = argparse.ArgumentParser()
parser.add_argument('--email', required=True, help='Email address for subscription')
args = parser.parse_args()

#Entered email address
subscriber_email = args.email

# Initializing AWS clients and resources
try:
    ec2 = boto3.resource('ec2')
    s3 = boto3.resource("s3")
    s3_client = boto3.client("s3")
    sns_client = boto3.client('sns', region_name='us-east-1')
except Exception as e:
    print(f"Error initializing AWS services: {e}")
    exit(1)  # Exits the script on error

#Instance creation --------------------------------------------------------------
try:
    user_data = """#!/bin/bash
                yum update -y
                yum install -y httpd
                systemctl start httpd
                systemctl enable httpd

                mkdir -p /var/www/html/images

                image_url="https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg"
                #Downloads the image from the URL
                curl -s "$image_url" -o /var/www/html/images/image.jpg

                cat <<EOL > /var/www/html/index.html
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Instance Metadata</title>
                    </head>
                    <body>
                        <h1>Instance Metadata</h1>
                        <ul>
                            <li><strong>Instance ID:</strong> $(curl -s http://169.254.169.254/latest/meta-data/instance-id)</li>
                            <li><strong>Instance Type:</strong> $(curl -s http://169.254.169.254/latest/meta-data/instance-type)</li>
                            <li><strong>Availability Zone:</strong> $(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)</li>
                        </ul>
                        <h2>Downloaded Image</h2>
                        <img src="/images/image.jpg" alt="Downloaded Image">
                    </body>
                    </html>
                """

    key_pair = 'mykey'
    security_group_ids = [ 'sg-0347d77281741d7c9' ]

    tags = [{'Key': 'Name' , 'Value': 'Web server'}]

    new_instances = ec2.create_instances(
    ImageId = 'ami-0bb4c991fa89d4b9b',
    MinCount = 1,
    MaxCount = 1,
    InstanceType = 't2.nano',
    KeyName = key_pair,
    SecurityGroupIds=security_group_ids,
    UserData=user_data,
    TagSpecifications = [{'ResourceType': 'instance', 'Tags': tags}])

except Exception as e:
    print(f"Error creating instances or configuring user data: {e}")

#Bucket creation ----------------------------------------------------------------------
try:
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    bucket_name = f"{random_chars}-dwolski"
    s3.create_bucket(Bucket=bucket_name)

    s3_client.delete_public_access_block(Bucket=bucket_name)

    bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{bucket_name}/*"
                    }
                    ]
    }
    s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))

    #downloads the image from the URL and puts it into the bucket
    image_url = "http://devops.witdemo.net/logo.jpg"
    image_data = requests.get(image_url).content
    s3_client.put_object(Bucket=bucket_name, Key="logo.jpg", Body=image_data)

    #creates the index.html and puts it inside of the bucket
    index_html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>My S3 Website</title>
    </head>
    <body>
        <h1>Welcome to My S3 Website</h1>
        <p>Here's the image:</p>
        <img src="logo.jpg" alt="Logo">
    </body>
    </html>
    """

    s3.Object(bucket_name, "index.html").put(Body=index_html_content, ContentType="text/html")

    website_configuration={
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    bucket_website = s3.BucketWebsite(bucket_name)

    response = bucket_website.put(WebsiteConfiguration = website_configuration)

except Exception as e:
    print(f"Error creating S3 bucket or configuring it: {e}")

# Retrieve the bucket's website URL
bucket_website_url = f"http://{bucket_name}.s3-website-{s3.meta.client.meta.region_name}.amazonaws.com"

#Sending a message-----------------------------------------------------------------------
try:
    # Specify the ARN of the "redshiftSNS" topic
    topic_arn = 'arn:aws:sns:us-east-1:092907437712:DevOps'

    #Check if a subscription already exists for this email
    response = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
    for subscription in response['Subscriptions']:
        if subscriber_email == subscription['Endpoint']:
            print(f"Email {subscriber_email} is already subscribed.")
            break
    else:
            # Subscribe with email and request confirmation
        response_sub = sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=subscriber_email,
        ReturnSubscriptionArn=True
        )

        confirmation_message = "Please confirm your subscription to this topic by clicking the link below:\n\n" + response_sub['ResponseMetadata']['RequestId']

        print(f"Subscription request sent to {subscriber_email}. Waiting for confirmation...")

        while True:
            # Check if the subscription is confirmed
            response_sub = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)

            for subscription in response_sub['Subscriptions']:
                if subscriber_email == subscription['Endpoint']:
                    if 'PendingConfirmation' in subscription['SubscriptionArn']:
                        print("Subscription is still pending confirmation.")
                    else:
                        print("Subscription confirmed.")
                        break  # Exit the loop when the subscription is confirmed
            else:
                print("Waiting for confirmation...")
                time.sleep(20)  # Wait for 20 seconds before checking again
                continue
            break

        message = f"Thank you for subscribing to our service. We hope you will be satisfied. To unsubscribe, click the following link:\n\n{confirmation_message}"

        #Publish a message to the topic
        response_publish = sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject='Thank you for subscribing',
            MessageAttributes={
                'email': {
                    'DataType': 'String',
                    'StringValue': subscriber_email
                }
            }
        )

        print("Message sent. Message ID:", response_publish['MessageId'])
except Exception as e:
    print(f"Error sending messages or confirming subscription: {e}")

# #Printing to terminal ------------------------------------------------------------------
new_instances[0].wait_until_running()

time.sleep(30)

instance = new_instances[0]
instance.reload()

instance_dns = instance.public_dns_name
public_ip = instance.public_ip_address
instance_website = f'http://{instance_dns}'

time.sleep(30)

# Specify your key pair name (replace 'mykey' with your actual key pair name)
key_pair = 'mykey'

# Create the SCP, SSH and copy commands
cmd1 = f"scp -i {key_pair}.pem monitoring.sh ec2-user@{public_ip}:"
cmd2 = f'ssh -i {key_pair}.pem ec2-user@{public_ip} "chmod 700 monitoring.sh"'
cmd3 = f'ssh -i {key_pair}.pem ec2-user@{public_ip} "sudo ./monitoring.sh"'
cmd4 = f'scp -i {key_pair}.pem ec2-user@{public_ip}:/var/log/monitoring.txt .'

LOG_FILE="/var/log/monitoring.txt"


# Execute the SCP and SSH commands
try:
    subprocess.run(cmd1, shell=True, check=True)
    subprocess.run(cmd2, shell=True, check=True)
    subprocess.run(cmd3, shell=True, check=True)
    print("File copied and executed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error: {e}")

# Copies the monitoring.log file from the EC2 instance to my local folder
try:
    subprocess.run(cmd4, shell=True, check=True)
    print("monitoring.log copied to the local folder.")
except subprocess.CalledProcessError as e:
    print(f"Error copying monitoring.log: {e}")

webbrowser.open(instance_website)
webbrowser.open(bucket_website_url)

#Getting the dir of the script and making the txt file there
file_path = os.path.join(os.path.dirname(__file__), 'dwolski.website.txt')

#Adding the URL's to the file
with open(file_path, 'w') as file:
    file.write('Instance Website URL: ' + instance_website + '\n')
    file.write('Bucket Website URL: ' + bucket_website_url + '\n')

print ('Instance ' + new_instances[0].id + ' is Running')
print ('Instance Website URL:', instance_website)
print ('Bucket Name:', bucket_name)
print('Bucket Website URL:', bucket_website_url)