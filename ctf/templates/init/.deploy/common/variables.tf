variable "incus_remote" {
  default = "local"
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

variable "ctf_acl_network" {
  default = "simulated-production-acl"
  type    = string
}

locals {
  track = yamldecode(file("${path.module}/../track.yaml"))
}
