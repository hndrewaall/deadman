provider "aws" {
  region = "us-east-1"
}

terraform {
  backend "s3" {
    region ="us-east-1"
    bucket = "deadman.gbre.org-tfstate"
    key    = "main"
  }
}

resource "aws_s3_bucket" "main" {
  bucket = "deadman.gbre.org-main"
  acl    = "private"
}

resource "aws_ses_template" "expired" {
  name    = "deadman_gbre-expired"
  subject = "[deadman] [ALERT] Watchdog expired!"
  html    = <<EOT
            <h1>Watchdog expired!</h1>
            <p>
            Watchdog has expired. Last updated: {{last_updated}} <br /> <br />
            <code>
            $ brew install openssl@1.1 <br />
            [...] <br />
            $ export PATH="/usr/local/opt/openssl@1.1/bin:$PATH" <br />
            $ openssl version <br />
            OpenSSL 1.1.1k  25 Mar 2021 <br />
            $ echo '{{ciphertext}}' | openssl aes-256-cbc -a -d -salt -pbkdf2 <br />
            [...]
            </code>
            </p>
            EOT
  text    = <<EOT
            Watchdog expired!

            Watchdog has expired. Last updated: {{last_updated}}

            $ brew install openssl@1.1
            [...]
            $ export PATH="/usr/local/opt/openssl@1.1/bin:$PATH"
            $ openssl version
            OpenSSL 1.1.1k  25 Mar 2021
            $ echo '{{ciphertext}}' | openssl aes-256-cbc -a -d -salt -pbkdf2
            [...]
            EOT
}

resource "aws_ses_email_identity" "main" {
  email = "hndrewaall@gmail.com"
}

resource "aws_sns_topic" "ses_failures" {
  name = "deadman-ses-failures"
}

resource "aws_ses_configuration_set" "main" {
  name = "deadman-main"
  reputation_metrics_enabled = true
}

resource "aws_ses_event_destination" "sns" {
  name                   = "deadman-sns"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true
  matching_types         = ["send", "reject", "bounce", "complaint", "delivery", "open", "click", "renderingFailure"]

  sns_destination {
    topic_arn = aws_sns_topic.ses_failures.arn
  }
}

resource "aws_ses_event_destination" "cloudwatch" {
  name                   = "deadman-cloudwatch"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true
  matching_types         = ["send", "reject", "bounce", "complaint", "delivery", "open", "click", "renderingFailure"]

  cloudwatch_destination {
    default_value  = "default"
    dimension_name = "dimension"
    value_source   = "emailHeader"
  }
}
