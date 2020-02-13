#!/bin/bash

cp terraform.tfvars.template terraform.tfvars
LOCATION='koreacentral'
HANA_V1_SN_RESOURCE_GROUP_NAME='rsg-hanaholv1'

az group create --location $LOCATION --name $HANA_V1_SN_RESOURCE_GROUP_NAME  
DOMAIN_NAME=domhanaholv1$RANDOM
VM_SIZE='Standard_E8s_v3'
VM_USERNAME='labuser'

sed -i "s/VAR_RESOURCE_GROUP/$HANA_V1_SN_RESOURCE_GROUP_NAME/" ./terraform.tfvars  
sed -i "s/VAR_LOCATION/$LOCATION/" ./terraform.tfvars  
sed -i "s/VAR_DOMAIN_NAME/$DOMAIN_NAME/" ./terraform.tfvars  
sed -i "s/VAR_VM_SIZE/$VM_SIZE/" ./terraform.tfvars  
sed -i "s/VAR_VM_USERNAME/$VM_USERNAME/" ./terraform.tfvars

SAPCAR_LINUX_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPCAR_1311-80000935.EXE?sp=r&st=2020-02-13T05:59:42Z&se=2022-02-13T13:59:42Z&spr=https&sv=2019-02-02&sr=b&sig=GF8u2mcNvp8E%2BCZXLc'
SAPCAR_LINUX_URL_REGEX="$(echo $SAPCAR_LINUX_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"
SAPCAR_WINDOWS_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPCAR_1311-80000938.EXE?sp=r&st=2020-02-13T06:01:26Z&se=2022-02-13T14:01:26Z&spr=https&sv=2019-02-02&sr=b&sig=ut%2FSNlG1JjFHfoXn62aXL5hnmnVeiWWkvIELQ3vmOpM%3D'
SAPCAR_WINDOWS_URL_REGEX="$(echo $SAPCAR_WINDOWS_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

HDBSERVER_URL='https://terraformstate0000.blob.core.windows.net/sap/IMDB_SERVER100_122_29-10009569.SAR?sp=r&st=2020-02-13T06:02:40Z&se=2022-02-13T14:02:40Z&spr=https&sv=2019-02-02&sr=b&sig=zc8pL7creucm7cR9qbVp1g%2BRtRl%2FPoVv%2FxBXTADUSUc%3D'
HDBSERVER_URL_REGEX="$(echo $HDBSERVER_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

SAP_HOST_AGENT_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPHOSTAGENT36_36-20009394.SAR?sp=r&st=2020-02-13T06:04:06Z&se=2022-02-13T14:04:06Z&spr=https&sv=2019-02-02&sr=b&sig=MGAeNa%2BRqgfuKNvTrFJSqh%2FHRm8%2BO7YTX%2FEGhr12sbM%3D'
SAP_HOST_AGENT_URL_REGEX="$(echo $SAP_HOST_AGENT_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

HANA_STUDIO_WINDOWS_URL='https://terraformstate0000.blob.core.windows.net/sap/IMC_STUDIO2_245_0-80000323.SAR?sp=r&st=2020-02-13T06:04:45Z&se=2022-02-13T14:04:45Z&spr=https&sv=2019-02-02&sr=b&sig=4Ydlwy68Uy4GEGMGECq5MrVfZJpKBzIlQmMO10vEu7I%3D'
HANA_STUDIO_WINDOWS_URL_REGEX="$(echo $HANA_STUDIO_WINDOWS_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

sed -i "s/VAR_SAPCAR_LINUX_URL/$SAPCAR_LINUX_URL_REGEX/" ./terraform.tfvars
sed -i "s/VAR_SAPCAR_WINDOWS_URL/$SAPCAR_WINDOWS_URL_REGEX/" ./terraform.tfvars
sed -i "s/VAR_HDBSERVER_URL/$HDBSERVER_URL_REGEX/" ./terraform.tfvars
sed -i "s/VAR_SAP_HOST_AGENT_URL/$SAP_HOST_AGENT_URL_REGEX/" ./terraform.tfvars
sed -i "s/VAR_HANA_STUDIO_WINDOWS_URL/$HANA_STUDIO_WINDOWS_URL_REGEX/" ./terraform.tfvars

SAPADMUSER_PASSWORD='Demo@pass123'
ADMUSER_PASSWORD='Demo@pass123'
DBSYSTEMUSER_PASSWORD='Demo@pass123'
DBXSAADMIN_PASSWORD='Demo@pass123'
DBSYSTEMTENANTUSER_PASSWORD='Demo@pass123'
DBSHINEUSER_PASSWORD='Demo@pass123'
WINDOWS_ADMIN_PASSWORD='Demo@pass123'

sed -i "s/VAR_SAPADMUSER_PASSWORD/$SAPADMUSER_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_ADMUSER_PASSWORD/$ADMUSER_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_DBSYSTEMUSER_PASSWORD/$DBSYSTEMUSER_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_DBXSAADMIN_PASSWORD/$DBXSAADMIN_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_DBSYSTEMTENANTUSER_PASSWORD/$DBSYSTEMTENANTUSER_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_DBSHINEUSER_PASSWORD/$DBSYSTEMTENANTUSER_PASSWORD/" ./terraform.tfvars  
sed -i "s/VAR_WINDOWS_ADMIN_PASSWORD/$WINDOWS_ADMIN_PASSWORD/" ./terraform.tfvars
