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
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "RDS_DB_NAME"
    value     = "ebdb"
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "RDS_USERNAME"
    value     = "betterbeauty"
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "RDS_PASSWORD"
    value     = "2vKcFBV8q5yR923RNh7P"
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "RDS_HOSTNAME"
    value     = "made-test-db"
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "RDS_PORT"
    value     = "5432"
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

# data "aws_db_instance" "made-test-db" {
#   db_instance_identifier = "made-test-db"
#   identifier           = "made-test-db"
#   allocated_storage    = 10
#   storage_type         = "gp2"
#   engine               = "postgres"
#   engine_version       = "10.4"
#   instance_class       = "db.t2.micro"
#   name                 = "ebdb"
#   username             = "betterbeauty"
#   password             = "2vKcFBV8q5yR923RNh7P"
#   #parameter_group_name = "default.mysql5.7"
#   apply_immediately    = true
#   backup_retention_period = 2 # days
#   backup_window       = "05:00-06:00"
#   maintenance_window  = "Tue:06:00-Tue:07:00"
#   final_snapshot_identifier = "made-test-db-final-snapshot"
#   multi_az             = true
# }


##############################################################
# Data sources to get VPC, subnets and security group details
##############################################################
data "aws_vpc" "default" {
  default = true
}

data "aws_subnet_ids" "all" {
  vpc_id = "${data.aws_vpc.default.id}"
}

data "aws_security_group" "default" {
  vpc_id = "${data.aws_vpc.default.id}"
  name   = "default"
}

# For RDS configuration documentation see: https://github.com/terraform-aws-modules/terraform-aws-rds
# For all parameters see: https://github.com/terraform-aws-modules/terraform-aws-rds/blob/master/main.tf
# Example is here: https://github.com/terraform-aws-modules/terraform-aws-rds/blob/master/examples/complete-postgres/main.tf
module "db" {
  source = "terraform-aws-modules/rds/aws"

  identifier = "made-test-db"

  engine            = "postgres"
  engine_version    = "10.4"
  instance_class    = "db.t2.micro"
  allocated_storage = 10 # GiB

  name     = "ebdb"
  username = "betterbeauty"
  password = "2vKcFBV8q5yR923RNh7P!"
  port     = "5432"

  #multi_az = true
  backup_retention_period = 1

  #iam_database_authentication_enabled = true

  vpc_security_group_ids = ["${data.aws_security_group.default.id}"]

  backup_window       = "05:00-06:00"
  maintenance_window  = "Tue:06:00-Tue:07:00"

  tags = {
    Owner       = "tigran"
    Environment = "test"
  }

  # DB subnet group
  subnet_ids = ["${data.aws_subnet_ids.all.ids}"]

  # DB parameter group
  family = "postgres10"
  db_subnet_group_name = "default"
  parameter_group_name = "default.postgres10"

  # Snapshot name upon DB deletion
  final_snapshot_identifier = "made-test-db-final-snapsho"
}

# resource "aws_db_instance" "made-test-db" {
#   db_instance_identifier = "made-test-db"
# }


output "made_test_db_endpoint" {
  value = "${module.db.this_db_instance_endpoint}"
}

output "made_test_db_address" {
  value = "${module.db.this_db_instance_address}"
}