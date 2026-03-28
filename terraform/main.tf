terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "bettingbot-terraform-state-818416606318"
    key    = "terraform.tfstate"
    region = "us-west-1"
  }
}

provider "aws" {
  region = var.aws_region
}
