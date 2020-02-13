#!/bin/bash

cp terraform.tfvars.template terraform.tfvars
LOCATION='koreacentral'
HANA_V1_SN_RESOURCE_GROUP_NAME='hanahol-rg'

#az group create --location $LOCATION --name $HANA_V1_SN_RESOURCE_GROUP_NAME  
DOMAIN_NAME=domhanaholv1$RANDOM
VM_SIZE='Standard_E8s_v3'
VM_USERNAME='labuser'

sed -i "s/VAR_RESOURCE_GROUP/$HANA_V1_SN_RESOURCE_GROUP_NAME/" ./terraform.tfvars  
sed -i "s/VAR_LOCATION/$LOCATION/" ./terraform.tfvars  
sed -i "s/VAR_DOMAIN_NAME/$DOMAIN_NAME/" ./terraform.tfvars  
sed -i "s/VAR_VM_SIZE/$VM_SIZE/" ./terraform.tfvars  
sed -i "s/VAR_VM_USERNAME/$VM_USERNAME/" ./terraform.tfvars

SAPCAR_LINUX_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPCAR_1311-80000935.EXE?sp=r&st=2020-02-13T07:17:55Z&se=2025-02-13T15:17:55Z&spr=https&sv=2019-02-02&sr=b&sig=Y4svp7XvSqUeIdlrThrBLkJyrA%2Brkg7YRjDgeXj%2Bcog%3D'
SAPCAR_LINUX_URL_REGEX="$(echo $SAPCAR_LINUX_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"
SAPCAR_WINDOWS_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPCAR_1311-80000938.EXE?sp=r&st=2020-02-13T07:21:16Z&se=2025-02-13T15:21:16Z&spr=https&sv=2019-02-02&sr=b&sig=1JSZ5zUYdl3CqsEFN0uSeD0RXbJ88PyZVQalPUxrtIg%3D'
SAPCAR_WINDOWS_URL_REGEX="$(echo $SAPCAR_WINDOWS_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

HDBSERVER_URL='https://terraformstate0000.blob.core.windows.net/sap/IMDB_SERVER100_122_29-10009569.SAR?sp=r&st=2020-02-13T07:22:40Z&se=2025-02-13T15:22:40Z&spr=https&sv=2019-02-02&sr=b&sig=OsR9um%2FaTyCMKYS4OkZZjw6V6ifvgaQbbupWlu4Jrs0%3D'
HDBSERVER_URL_REGEX="$(echo $HDBSERVER_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

SAP_HOST_AGENT_URL='https://terraformstate0000.blob.core.windows.net/sap/SAPHOSTAGENT36_36-20009394.SAR?sp=r&st=2020-02-13T07:24:08Z&se=2025-02-13T15:24:08Z&spr=https&sv=2019-02-02&sr=b&sig=A4aa7q3hBs82cekbvXbZtZBXGjiuUCu4Kby9T9Sw8GI%3D'
SAP_HOST_AGENT_URL_REGEX="$(echo $SAP_HOST_AGENT_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')"

HANA_STUDIO_WINDOWS_URL='https://terraformstate0000.blob.core.windows.net/sap/IMC_STUDIO2_245_0-80000323.SAR?sp=r&st=2020-02-13T07:25:09Z&se=2025-02-13T15:25:09Z&spr=https&sv=2019-02-02&sr=b&sig=NiuGX4cmisHokdbC6wmh3xc9Fin%2F1V9yQ%2FwPL%2BPWw4g%3D'
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
