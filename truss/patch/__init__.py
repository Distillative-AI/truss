from pathlib import Path
from typing import Dict, List

from truss.patch.hash import file_content_hash_str
from truss.patch.types import TrussSignature
from truss.templates.control.control.helpers.types import (
    Action,
    ModelCodePatch,
    Patch,
    PatchType,
)
from truss.truss_spec import TrussSpec


def calc_truss_patch(
    truss_dir: Path, previous_truss_signature: TrussSignature
) -> List[Patch]:
    changed_paths = _calc_changed_paths(
        truss_dir, previous_truss_signature.content_hashes_by_path
    )
    # todo calcuate model code patches onlye for now, add config changes later
    truss_spec = TrussSpec(truss_dir)
    model_module_path = str(truss_spec.model_module_dir.relative_to(truss_dir))

    patches = []
    for path in changed_paths["removed"]:
        if path.startswith(model_module_path):
            relative_to_model_module_path = str(
                Path(path).relative_to(model_module_path)
            )
            patches.append(
                Patch(
                    type=PatchType.MODEL_CODE,
                    body=ModelCodePatch(
                        action=Action.REMOVE,
                        path=relative_to_model_module_path,
                    ),
                )
            )

    for path in changed_paths["added"] + changed_paths["updated"]:
        if path.startswith(model_module_path):
            full_path = truss_dir / path
            relative_to_model_module_path = str(
                Path(path).relative_to(model_module_path)
            )

            # TODO(pankaj) Add support for empty directories, skip them for now.
            if not full_path.is_file():
                continue

            with full_path.open() as file:
                content = file.read()
            patches.append(
                Patch(
                    type=PatchType.MODEL_CODE,
                    body=ModelCodePatch(
                        action=Action.UPDATE,
                        path=relative_to_model_module_path,
                        content=content,
                    ),
                )
            )
    return patches


def _calc_changed_paths(
    root: Path, previous_root_path_content_hashes: Dict[str, str]
) -> dict:
    """
    TODO(pankaj) add support for directory creation in patch
    """
    root_relative_paths = set(
        (str(path.relative_to(root)) for path in root.glob("**/*"))
    )
    previous_root_relative_paths = set(previous_root_path_content_hashes.keys())

    added_paths = root_relative_paths - previous_root_relative_paths
    removed_paths = previous_root_relative_paths - root_relative_paths

    updated_paths = set()
    common_paths = root_relative_paths.intersection(previous_root_relative_paths)
    for path in common_paths:
        full_path: Path = root / path
        if full_path.is_file():
            content_hash = file_content_hash_str(full_path)
            previous_content_hash = previous_root_path_content_hashes[path]
            if content_hash != previous_content_hash:
                updated_paths.add(path)

    return {
        "added": list(added_paths),
        "updated": list(updated_paths),
        "removed": list(removed_paths),
    }
