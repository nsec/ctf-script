resource "incus_network_acl" "simulated_production_acl" {
  remote = var.incus_remote

  name        = var.ctf_acl_network
  description = "Simulate production ACL."

  egress = [
    {
      action           = "allow"
      destination      = "2606:4700:10::/48"
      protocol         = "tcp"
      destination_port = "80"
      description      = "archive.ubuntu.com"
      state            = "enabled"
    },
    {
      action           = "allow"
      destination      = "2a04:4e42:20::644"
      protocol         = "tcp"
      destination_port = "80"
      description      = "deb.debian.org"
      state            = "enabled"
    },
    {
      action           = "allow"
      protocol         = "tcp"
      destination_port = "53"
      description      = "DNS over TCP"
      state            = "enabled"
    },
    {
      action           = "allow"
      protocol         = "udp"
      destination_port = "53"
      description      = "DNS over UDP"
      state            = "enabled"
    }
  ]

  ingress = [
    {
      action = "allow"
      state  = "enabled"
    }
  ]
}
output "ctf_acl_network" {
  value = incus_network_acl.simulated_production_acl.name
}
