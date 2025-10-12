variable "incus_remote" {
  default = "local"
  type    = string
}

variable "deploy" {
  default = "dev"
  type    = string
}

variable "build_container" {
  default = false
  type    = bool
}

variable "ctf_dns_network_zone" {
  default = "ctf"
  type = string
}

locals {
  track = yamldecode(file("${path.module}/../track.yaml"))
}
