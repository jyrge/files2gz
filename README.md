# files2gz

A simple and stupid service for watching a directory and copying all files created in the directory
to another directory, compressed using gzip.

## Dependencies

**Python >= 3.10** (tested with 3.12.5), for the file compressing service <br/>
**Ansible >= 2.11** (tested with 2.17.3), for remote deployment with Ansible <br/>
**Docker**, for containerized deployment

### pip packages

**watchdog 4.0.2**

### Ansible collections

**Community.Docker**, containing plugins for managing Docker images and containers on managed nodes

### Other dependencies

`sshpass` - required for Ansible deployments, if using a password for authenticating to the hosts

## Development environment

Clone this repository

`git clone https://github.com/jyrge/files2gz`

and switch into the directory. Initialize a new virtual environment for Python:

`python -m venv .venv`

To activate the virtual environment, use the activation scripts provided by the virtual environment.
Next example applies to Unix-like environments:

`source .venv/bin/activate`

Install the pip dependencies with

`pip install -r requirements.txt`

Use the text editor or IDE of your choice for development.

## Running the service

After performing the steps described above, you can start the service by running the files2gz.py script with

`python files2gz.py [OPTIONS]`

The available options are described below.

```
usage: files2gz [-h] [--source SOURCE] [--target TARGET] [--log-dir LOG_DIR]
                [--log-level LOG_LEVEL]

Monitor files in a directory and send them to another directory compressed.

options:
  -h, --help            show this help message and exit
  --source SOURCE       path to the directory being monitored
  --target TARGET       path to the target directory for compressed files
  --log-dir LOG_DIR     path to the directory, in which the logs will be
                        stored
  --log-level LOG_LEVEL
                        minimum log level for the events being logged
```

`--source` and `--target` options are required. Default directory for logs is `<project-dir>/logs` and logging level `INFO`,
if the parameters are omitted.

You can also pass the command-line arguments via environment variables, with the following mapping:

`FILES2GZ_SOURCE_DIR` - `--source`<br/>
`FILES2GZ_TARGET_DIR` - `--target`<br/>
`FILES2GZ_LOG_DIR` - `--log-dir`<br/>
`FILES2GZ_LOG_LEVEL` - `--log-level`

While running, the service monitors file events in the directory indicated by the `--source` argument. When new files are created,
the service copies the files to the target directory, compressed with gzip. If directories are copied to the directory being monitored,
the files in the directory are processed recursively and placed in the corresponding directory in target directory. By default, events
are logged in both log files stored in the specified log directory and in stderr. If the log directory is inaccessible, the logs are only
printed in stderr.

The service terminates on receiving SIGINT (for example, via keyboard interrupt Ctrl+C) or SIGTERM.

## Running the service containerized

### Building the image

To run the service containerized, you must build the Docker image first (if the image doesn't already exist).
Make sure that Docker is installed in your system, Docker daemon is running, and that your user belongs to the
`docker` group (on Linux).

For example, to build the image with the name `files2gz` and tag `v1`, run the following command in the project
directory:

`docker build -t files2gz:v1 .`

After the build process completes, you can verify that the image is present by running `docker images`.

### Starting the container from the image

To run the container in the background with name `files2gz` from image named `files2gz:v1`, replace the paths from the following command
with the **absolute** paths on host and run the command:

`docker run --name files2gz -d --mount type=bind,src="path-to-source-dir-on-host",target="/app/source" --mount type=bind,src="path-to-target-dir-on-host",target="/app/target" --mount type=bind,src="path-to-log-dir-on-host",target="/app/logs" files2gz:v1`

The command starts the service containerized. The source, target, and log directories are bind mounted to the container from the host
file system. By default, the process is run as `root` user. With `--user` flag, you can optionally provide a non-root user for running
the process.

### Starting, stopping and removing the container

After the container is created, the service can be stopped, started, restarted and removed just as any other Docker container.

## Deploying the service to a managed remote node using Ansible

Ansible playbooks for deploying the service can be found in `ansible-files` directory. Make sure that you have installed all the
dependencies for Ansible in the controller node. To check that you have the Community.Docker collection installed, run:

`ansible-galaxy collection list community.docker`

The Ansible playbooks and other resources in the directory are organized as follows:

`inventory.example.yaml` - Example of the inventory file, containing the configuration for the managed nodes. Copy to 
`inventory.yaml` and modify it to suit your configuration.<br/>
`vars.example.yaml` - Example of the file containing variables, such as the source dir, target dir, log dir, and the log level
in the host side. Copy to `vars.yaml` and modify the paths if needed. By default, the paths point to the home directory of the
login user.<br/>
`setup.yaml` - Playbook for setting up the host for running Docker.<br/>
`build.yaml` - Playbook for cloning this repository from GitHub and building the Docker image.<br/>
`run.yaml` - Playbook for running the service containerized.<br/>
`stop.yaml` - Playbook for stopping and removing the service container.<br/>
`main.yaml` - Runs the "setup", "build", and "run" playbooks.

**Note:** `setup.yaml` playbook currently only supports Debian, Ubuntu, and Arch Linux distributions. You are free to implement
support for other distros, if you wish.

**Note 2:** This configuration is only tested on a managed remote node running Debian 12 via ssh connection.

### Running playbooks

After installing the required dependencies, clone this repository on a controller node and change to `ansible-files` directory
in the project directory.

Copy the example inventory and vars files into `inventory.yaml` and `vars.yaml`. Modify the configuration to suit your needs,
as instructed in the comments. Set the directory paths and log level in `vars.yaml`.

You can run the playbooks with the following command:

`ansible-playbook -i inventory.yaml <playbook-filename>`

You can either run the playbooks individually or run the "setup", "build" and "run" playbooks subsequently by executing `main.yaml`.

To stop and remove the service container, run the `stop.yaml` playbook. Please note that this doesn't remove the data created by the
service in the managed node.

## Known caveats

* Recursive file watching doesn't work, while running the service containerized on macOS.
