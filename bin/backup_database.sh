#!/bin/bash

DB_NAME=$1
DB_USERNAME=$2
# Set PGPASSWORD as pg_dump uses this env var.
DB_PASSWORD=$3


function file_name(){
    echo ${BACKUP_DIR}/${DB_NAME}_$(date '+%Y%m%d_%H%M%S').sql
}

if [[ (-z $DB_NAME) || (-z $DB_USERNAME) || (-z $DB_PASSWORD) ]] ; then
    echo "Expecting command to be of form ./backup_database.sh <db_name> <db_username> <db_password>"
    exit 1
fi

# currently the backup directory is hard coded
BACKUP_DIR=~/seed-backups
mkdir -p $BACKUP_DIR

export PGPASSWORD=$DB_PASSWORD
echo "pg_dump -U $DB_USERNAME -Fc $DB_NAME > $(file_name)"
pg_dump -U $DB_USERNAME -Fc $DB_NAME > $(file_name)
unset PGPASSWORD