import requests
from typing import Optional, List, Dict, Any

class ModrinthClient:
    BASE_URL = "https://api.modrinth.com/v2"

    def __init__(self, user_agent: str = "DonutDownloader/1.0.0"):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def get_project(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch project metadata from Modrinth.
        """
        try:
            url = f"{self.BASE_URL}/project/{slug_or_id}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_versions(self, slug_or_id: str, loaders: Optional[List[str]] = None, game_versions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch versions for a project, optionally filtered by loaders and game versions.
        """
        try:
            url = f"{self.BASE_URL}/project/{slug_or_id}/version"
            params = {}
            if loaders:
                # Format: ["fabric", "quilt"] -> '["fabric", "quilt"]'
                params["loaders"] = str(loaders).replace("'", '"')
            if game_versions:
                 params["game_versions"] = str(game_versions).replace("'", '"')
            
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def get_version_dependencies(self, version_id: str) -> List[Dict[str, Any]]:
        """
        Get dependencies for a specific version ID.
        NOTE: The /version/{id} endpoint returns the version object which contains 'dependencies'.
        """
        try:
            url = f"{self.BASE_URL}/version/{version_id}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("dependencies", [])
        except Exception:
            return []

    def get_project_dependencies(self, slug_or_id: str) -> List[Dict[str, Any]]:
        """
        Get all dependencies for a project using the project dependencies endpoint.
        """
        try:
            url = f"{self.BASE_URL}/project/{slug_or_id}/dependencies"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("projects", [])
        except Exception:
            return []

    def resolve_latest_valid_version(self, slug_or_id: str, loaders: List[str], game_versions: List[str]) -> Optional[Dict[str, Any]]:
        """
        Finds the latest version that matches the criteria and returns it (with dependencies embedded).
        """
        versions = self.get_versions(slug_or_id, loaders, game_versions)
        if not versions:
            return None
        return versions[0] # API sorting is usually date desc, so first is latest
