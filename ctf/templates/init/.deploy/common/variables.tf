variable "incus_remote" {
  default = var.incus_remote
  type    = string
}

variable "incus_vm_remote" {
  default = null
  type    = string
}

variable "incus_vm_project" {
  default = null
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

variable "already_deployed" {
  default = false
  type    = bool
}

variable "ctf_dns_network_zone" {
  default = "ctf"
  type    = string
}

locals {
  track = yamldecode(file("${path.module}/../track.yaml"))
}
