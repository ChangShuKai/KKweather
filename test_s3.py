import boto3

s3 = boto3.client('s3', config=boto3.session.Config(signature_version=boto3.session.botocore.UNSIGNED))
resp = s3.list_objects_v2(Bucket='noaa-himawari9', Prefix='AHI-L1b-FLDK/2024/01/01/', Delimiter='/')
print("Prefixes:", [x['Prefix'] for x in resp.get('CommonPrefixes', [])])
if resp.get('CommonPrefixes'):
    prefix = resp['CommonPrefixes'][0]['Prefix']
    print(f"Checking {prefix}")
    resp2 = s3.list_objects_v2(Bucket='noaa-himawari9', Prefix=prefix)
    print("Files:", [x['Key'] for x in resp2.get('Contents', [])][:5])
