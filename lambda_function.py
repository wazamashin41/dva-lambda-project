import json
import boto3
import time
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# これを実行すると、boto3（DynamoDB通信）をX-Rayが自動で追跡し始めます
patch_all()

# DynamoDBの準備
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch') # メトリクス送信に使用します
table = dynamodb.Table('DVA-Test-Table')
# table = dynamodb.Table('WRONG-TABLE-NAME') # テーブル名をわざと間違えてデプロイ

def lambda_handler(event, context):
    # 1. プロキシ統合経由で「ステージ変数」を取得
    # event['stageVariables'] から 'env' (dev か prod) を取り出す
    stage_vars = event.get('stageVariables', {})
    alias = stage_vars.get('env', 'unknown')
    
    print(f"Executing for alias: {alias}")

    # --- モニタリング開始：DynamoDB処理の時間を計る ---
    start_time = time.time()

    # 2. DynamoDBのカウントアップ処理
    response = table.update_item(
        Key={'id': 'visitor_count'},
        UpdateExpression="ADD count_num :inc",
        ExpressionAttributeValues={':inc': 1},
        ReturnValues="UPDATED_NEW"
    )
    
    # --- モニタリング終了・送信 ---
    duration = (time.time() - start_time) * 1000 # ミリ秒換算

    # カスタムメトリクスの送信
    cloudwatch.put_metric_data(
        Namespace='MyService/VisitorApp',
        MetricData=[
            {
                'MetricName': 'DBUpdateLatency',
                'Value': duration,
                'Unit': 'Milliseconds',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': alias}, # dev か prod かを識別
                    {'Name': 'FunctionName', 'Value': context.function_name}
                ]
            }
        ]
    )

    new_count = response['Attributes']['count_num']

    # 3. プロキシ統合用のレスポンス形式
    message = f"Hello! You are visitor number {new_count} in the [{alias}] environment."

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(message)
    }
    
    # 502 Bad Gatewayを意図的に発生させる{"message": "Internal server error"}
    # return "hello"

