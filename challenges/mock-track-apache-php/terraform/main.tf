resource "incus_project" "this" {
  remote = var.incus_remote

  name        = local.track.name
  description = "Project for the ${local.track.name} track"

  config = {
    "features.images"       = "false"
    "user.contacts.dev"     = join(", ", local.track.contacts.dev)
    "user.contacts.qa"      = join(", ", local.track.contacts.qa)
    "user.contacts.support" = join(", ", local.track.contacts.support)
  }
}

resource "incus_network" "this" {
  remote  = var.incus_remote
  project = incus_project.this.name

  name        = substr(local.track.name, 0, 15)
  description = "Network for challenges in the ${local.track.name} track"

  config = {
    "ipv4.address" = var.deploy == "production" ? "none" : null
    "ipv6.address" = "9000:d37e:c40b:c5e8::1/64"
    "ipv6.nat"     = var.deploy == "production" ? "false" : "true"
  }
}

resource "incus_profile" "this" {
  remote  = var.incus_remote
  project = incus_project.this.name

  name        = "containers"
  description = "Default profile for containers in the ${local.track.name} track"

  config = {
    "limits.cpu"              = "2"
    "limits.memory"           = "256MiB"
    "limits.processes"        = "2000"
    "environment.http_proxy"  = var.deploy == "production" ? "http://proxy.ctf-int.internal.nsec.io:3128" : null
    "environment.https_proxy" = var.deploy == "production" ? "http://proxy.ctf-int.internal.nsec.io:3128" : null
  }


  device {
    name = "root"
    type = "disk"

    properties = {
      "pool" = "default"
      "path" = "/"
      "size" = "1GiB"
    }
  }
}


locals {
  instances = {
    mock-track-apache-php = {
      "description" : "Main apache + PHP website",
      "hwaddr" : "00:16:3e:d5:1c:a1",
      "record" : "mock-track-apache-php",
      "ipv6" : "216:3eff:fed5:1ca1"
    }
  }
}

resource "incus_instance" "this" {
  remote  = var.incus_remote
  project = incus_project.this.name

  for_each = local.instances

  name = each.key

  image    = "images:debian/13"
  profiles = ["default", incus_profile.this.name]

  device {
    name = "eth0"
    type = "nic"

    properties = {
      "network" = incus_network.this.name
      "name"    = "eth0"
      "hwaddr"  = "${each.value["hwaddr"]}"
    }
  }

  lifecycle {
    ignore_changes = [running]
  }
}

resource "incus_network_zone_record" "this" {
  for_each = local.instances

  zone = "ctf"

  name        = each.value["record"]
  description = each.value["description"]

  entry {
    type  = "AAAA"
    ttl   = 3600
    value = "9000:d37e:c40b:c5e8:${each.value["ipv6"]}"
  }
}
