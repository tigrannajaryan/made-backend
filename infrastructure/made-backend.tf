provider "aws" {
  region     = "${var.region}"
}

# For Elasticbeanstalk configuration Terraform doc see
# https://www.terraform.io/docs/providers/aws/r/elastic_beanstalk_environment.html
# For the list of all settings available for Elasticbeanstalk see
# https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
resource "aws_elastic_beanstalk_application" "made-backend-test-app" {
  name        = "made-backend-test"
  description = "Made Test Backend created via Terraform"
}

resource "aws_elastic_beanstalk_environment" "made-backend-test-env" {
  name                = "made-backend-test-env"
  application         = "${aws_elastic_beanstalk_application.made-backend-test-app.name}"
  solution_stack_name = "64bit Amazon Linux 2018.03 v2.7.3 running Python 3.6"

  # We want exactly 2 instances (min=max=2)
  setting {
    namespace = "aws:autoscaling:asg"
    name = "MinSize"
    value = "2"
  }
  setting {
    namespace = "aws:autoscaling:asg"
    name = "MaxSize"
    value = "2"
  }

  # You can set the environment type, single or LoadBalanced
  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "EnvironmentType"
    value     = "LoadBalanced"
  }

  # Enable rolling deployments
  setting {
    namespace = "aws:elasticbeanstalk:command"
    name = "DeploymentPolicy"
    value = "Rolling"
  }

  # Enable Health based rolling configuration updates
  setting {
    namespace = "aws:autoscaling:updatepolicy:rollingupdate"
    name = "RollingUpdateEnabled"
    value = "true"
  }
  setting {
    namespace = "aws:autoscaling:updatepolicy:rollingupdate"
    name = "RollingUpdateType"
    value = "Health"
  }

  # One instance per deployment batch
  setting {
    namespace = "aws:elasticbeanstalk:command"
    name = "BatchSizeType"
    value = "Fixed"
  }
  setting {
    namespace = "aws:elasticbeanstalk:command"
    name = "BatchSize"
    value = "1"
  }

  # Set environment variables
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "LEVEL"
    value     = "staging"
  }

  # Disable HTTP listener
  setting {
    namespace = "aws:elb:listener"
    name = "ListenerEnabled"
    value = "false"
  }

  # Add HTTPS listener
  setting {
    namespace = "aws:elb:listener:443"
    name = "ListenerProtocol"
    value = "HTTPS"
  }
  setting {
    namespace = "aws:elb:listener:443"
    name = "InstancePort"
    value = "80"
  }
  setting {
    namespace = "aws:elb:listener:443"
    name = "InstanceProtocol"
    value = "HTTP"
  }
  setting {
    namespace = "aws:elb:listener:443"
    name = "SSLCertificateId"
    # *.betterbeauty.io SSL Certificate
    value = " arn:aws:acm:us-east-1:024990310245:certificate/534d5282-bb32-46fe-a10c-ca02816d75d5"
  }
}

