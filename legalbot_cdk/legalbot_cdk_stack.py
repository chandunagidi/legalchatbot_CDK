from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from constructs import Construct

class LegalbotCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: id, **kwargs) -> str:
        super().__init__(scope, construct_id, **kwargs)

        # 1. S3 Bucket for CUAD contracts
        contracts_bucket = s3.Bucket(
            self, "LegalbotContractsBucket",
            bucket_name="legalbot-cuad-contracts-dev-chandu",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # 2. IAM Role for Lambda with permissions for Bedrock and CloudWatch
        lambda_role = iam.Role(
            self, "LegalbotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add explicit inline policy for Bedrock Knowledge Base Retrieve & Generate
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:Retrieve",
                "bedrock:RetrieveAndGenerate",
                "bedrock:InvokeModel"
            ],
            resources=["*"]
        ))

        # 3. Lambda Function (matched to your working arm64 setup)
        legal_chatbot_lambda = _lambda.Function(
            self, "LegalbotChatLambda",
            function_name="legalbot-chat-cdk",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            role=lambda_role,
            # Add any environment variables from your console function here if needed:
            environment={
                "KB_ID": "TSMEYEQUFF",
                "MODEL_ID": "qwen.qwen3-32b-v1:0",
            }
        )

        # 4. Expose via Public Function URL (using FunctionUrlCorsOptions)
        function_url = legal_chatbot_lambda.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[_lambda.HttpMethod.POST, _lambda.HttpMethod.GET],
                allowed_headers=["*"]
            )
        )

        # Output the Function URL endpoint
        CfnOutput(
            self, "FunctionUrlOutput",
            value=function_url.url,
            description="Public Lambda Function URL Endpoint"
        )