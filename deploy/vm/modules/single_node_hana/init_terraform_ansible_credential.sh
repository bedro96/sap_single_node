#!/bin/bash
echo "Setting environment variables for Ansible"
#export ANSIBLE_AZURE_AUTH_SOURCE=msi
export AZURE_SUBSCRIPTION_ID=05be085b-86ea-4336-addc-38fd56051a9e
export AZURE_CLIENT_ID=f5202f78-5383-4463-9d2d-4d88461c02cb
export AZURE_SECRET=580afef1-8dfe-4858-9a01-72f503c27420
export AZURE_TENANT=72f988bf-86f1-41af-91ab-2d7cd011db47
echo "Setting environment variables for Terraform"
#export ARM_USE_MSI=true
export ARM_SUBSCRIPTION_ID=05be085b-86ea-4336-addc-38fd56051a9e
export ARM_CLIENT_ID=f5202f78-5383-4463-9d2d-4d88461c02cb
export ARM_CLIENT_SECRET=580afef1-8dfe-4858-9a01-72f503c27420
export ARM_TENANT_ID=72f988bf-86f1-41af-91ab-2d7cd011db47
export ARM_RESOURCE_GROUP=imgRepoRG
export TF_LOG=TRACE
export TF_LOG_PATH=~/TF_LOG/tflog.txt
