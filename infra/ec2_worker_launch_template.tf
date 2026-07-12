# Launch Template for EC2 Worker
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_launch_template" "ec2_worker_lt" {
  name_prefix   = "crypto-currency-ta-worker-"
  image_id      = data.aws_ami.amazon_linux_2.id
  instance_type = "t3.small"

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_worker_profile.name
  }

  vpc_security_group_ids = [aws_security_group.ec2_worker_sg.id]

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "crypto-currency-ta-worker"
    }
  }
}

output "ec2_worker_launch_template_id" {
  value = aws_launch_template.ec2_worker_lt.id
}
