# Security Group for EC2 Worker
resource "aws_security_group" "ec2_worker_sg" {
  name        = "crypto-currency-ta-ec2-worker-sg"
  description = "Security group for transient EC2 workers"

  # Inbound rules: None needed if using SSM and only performing outbound tasks.
  # We allow no inbound traffic for security.

  # Outbound rules: Allow all outbound traffic (default)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "crypto-currency-ta-ec2-worker-sg"
    Environment = "development"
  }
}

output "ec2_worker_security_group_id" {
  value = aws_security_group.ec2_worker_sg.id
}
