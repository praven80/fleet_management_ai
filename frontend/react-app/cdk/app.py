#!/usr/bin/env python
import aws_cdk as cdk
from frontend_stack import FrontendStack

app = cdk.App()
FrontendStack(app, "HertzFrontendStack")
app.synth()
