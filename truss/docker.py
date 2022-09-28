import logging
from typing import Dict, List

from truss.constants import TRUSS_DIR
from truss.local.local_config_handler import LocalConfigHandler


class Docker:
    _client = None

    @staticmethod
    def client():
        if Docker._client is None:
            from python_on_whales import DockerClient, docker

            if LocalConfigHandler.get_config().use_sudo:
                Docker._client = DockerClient(client_call=["sudo", "docker"])
            else:
                Docker._client = docker
        return Docker._client


def get_containers(labels: dict, all=False):
    """Gets containers given labels."""
    return Docker.client().container.list(
        filters=_create_label_filters(labels), all=all
    )


def get_images(labels: dict):
    """Gets images given labels."""
    return Docker.client().image.list(filters=_create_label_filters(labels))


def get_urls_from_container(container_details):
    """Gets url where docker container is hosted."""
    if (
        container_details.network_settings is None
        or container_details.network_settings.ports is None
    ):
        return {}
    ports = container_details.network_settings.ports

    def parse_port(port_protocol) -> int:
        return int(port_protocol.split("/")[0])

    def url_from_port_protocol_value(port_protocol_value: Dict[str, str]) -> str:
        return (
            "http://"
            + port_protocol_value["HostIp"]
            + ":"
            + port_protocol_value["HostPort"]
        )

    def urls_from_port_protocol_values(
        port_protocol_values: List[Dict[str, str]]
    ) -> List[str]:
        return [url_from_port_protocol_value(v) for v in port_protocol_values]

    return {
        parse_port(port_protocol): urls_from_port_protocol_values(value)
        for port_protocol, value in ports.items()
        if value is not None
    }


def kill_containers(labels: Dict[str, str]):
    containers = get_containers(labels)
    for container in containers:
        container_labels = container.config.labels
        if TRUSS_DIR in container_labels:
            truss_dir = container_labels[TRUSS_DIR]
            logging.info(f"Killing Container: {container.id} for {truss_dir}")
    Docker.client().container.kill(containers)


def get_container_logs(container):
    return Docker.client().container.logs(container, follow=True, stream=True)


def _create_label_filters(labels: dict):
    return {
        f"label={label_key}": label_value for label_key, label_value in labels.items()
    }
