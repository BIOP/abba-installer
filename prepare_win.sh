#!/bin/bash

# Change to the script's directory
cd "$(dirname "$0")"
current_folder=$(pwd)

# Define common functions and variables
download_file() {
  local url="$1"
  local output_file="$2"
  if [ ! -f "$output_file" ]; then
    curl -L "$url" -o "$output_file"
    if [ $? -ne 0 ]; then
      echo "Download failed. Check the URL or your internet connection."
      exit 1
    fi
  else
    echo "File already exists. Skipping download."
  fi
}

# Downloads DeepSlice models
base_url="https://data-proxy.ebrains.eu/api/v1/buckets/deepslice/weights/"
base_folder=${current_folder}"/envs/deepslice/lib/site-packages/DeepSlice/metadata/weights/"

model="xception_weights_tf_dim_ordering_tf_kernels.h5"
download_file "${base_url}${model}" "${base_folder}${model}"

model="Allen_Mixed_Best.h5"
download_file "https://data-proxy.ebrains.eu/api/v1/buckets/deepslice/weights/Allen_Mixed_Best.h5" "${base_folder}${model}"

model="Synthetic_data_final.hdf5"
download_file "${base_url}${model}" "${base_folder}${model}"

# Install a local Fiji inside the windows folder, updates it, and add the standard PTBIOP update sites

# For that, use the bash scripts already made in https://github.com/BIOP/biop-bash-scripts

if [ ! -d "${current_folder}/biop-bash-scripts" ]; then
  git clone https://github.com/BIOP/biop-bash-scripts.git
else
  echo "Biop bash scripts already cloned. Update the repo if necessary."
  cd biop-bash-scripts
  git pull
  cd ..
fi

# Run Fiji install scripts
# ./biop-bash-scripts/full_install_biop_fiji.sh "${current_folder}/win/"

# Create a package of files to ship with the installer
tar -cvzf abba-pack-win.tar.gz img win abba envs
