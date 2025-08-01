variable "incus_remote" {
  default = "local"
  type    = string
}

variable "deploy" {
  default = "dev"
  type    = string
}

locals {
  track = yamldecode(file("${path.module}/../track.yaml"))
}
