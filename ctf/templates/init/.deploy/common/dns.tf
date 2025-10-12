resource "incus_network_zone" "this" {
  remote = var.incus_remote

  name        = "ctf"
  description = "DNS zone for the internal .ctf TLD"
}

output "ctf_dns_network_zone" {
  value = incus_network_zone.this.name
}