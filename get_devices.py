#!/usr/bin/env python3
"""Script to fetch all device information from Kumo Cloud API."""

import asyncio
import json
import sys
from typing import Any

import aiohttp


API_BASE_URL = "https://app-prod.kumocloud.com"
API_VERSION = "v3"
API_APP_VERSION = "3.0.9"


class KumoCloudClient:
    """Simple Kumo Cloud API client."""

    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        self.access_token: str | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Login and get access token."""
        url = f"{API_BASE_URL}/{API_VERSION}/login"
        headers = {
            "x-app-version": API_APP_VERSION,
            "Content-Type": "application/json",
        }
        data = {
            "username": username,
            "password": password,
            "appVersion": API_APP_VERSION,
        }

        async with self.session.post(url, headers=headers, json=data) as response:
            if response.status == 403:
                raise Exception("Invalid username or password")
            response.raise_for_status()
            result = await response.json()
            self.access_token = result["token"]["access"]
            return result

    async def _request(self, endpoint: str) -> Any:
        """Make authenticated request."""
        url = f"{API_BASE_URL}/{API_VERSION}{endpoint}"
        headers = {
            "x-app-version": API_APP_VERSION,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def get_account_info(self) -> dict[str, Any]:
        """Get account information."""
        return await self._request("/accounts/me")

    async def get_sites(self) -> list[dict[str, Any]]:
        """Get all sites."""
        return await self._request("/sites/")

    async def get_zones(self, site_id: str) -> list[dict[str, Any]]:
        """Get zones for a site."""
        return await self._request(f"/sites/{site_id}/zones")

    async def get_device_details(self, device_serial: str) -> dict[str, Any]:
        """Get device details."""
        return await self._request(f"/devices/{device_serial}")

    async def get_device_profile(self, device_serial: str) -> list[dict[str, Any]]:
        """Get device profile."""
        return await self._request(f"/devices/{device_serial}/profile")


async def fetch_all_devices(username: str, password: str) -> dict[str, Any]:
    """Fetch all device information."""
    result = {
        "account": {},
        "sites": [],
    }

    async with KumoCloudClient() as client:
        # Login
        print("Logging in...", file=sys.stderr)
        await client.login(username, password)

        # Get account info
        print("Fetching account info...", file=sys.stderr)
        result["account"] = await client.get_account_info()

        # Get all sites
        print("Fetching sites...", file=sys.stderr)
        sites = await client.get_sites()

        for site in sites:
            site_id = site["id"]
            site_name = site["name"]
            print(f"Fetching zones for site: {site_name}...", file=sys.stderr)

            site_data = {
                "site_info": site,
                "zones": [],
            }

            # Get zones for this site
            zones = await client.get_zones(site_id)

            for zone in zones:
                zone_data = {
                    "zone_info": zone,
                    "device_details": None,
                    "device_profile": None,
                }

                # Check if zone has a device
                if "adapter" in zone and zone["adapter"]:
                    device_serial = zone["adapter"]["deviceSerial"]
                    print(f"  Fetching device {device_serial}...", file=sys.stderr)

                    # Fetch device details and profile in parallel
                    device_details, device_profile = await asyncio.gather(
                        client.get_device_details(device_serial),
                        client.get_device_profile(device_serial),
                    )

                    zone_data["device_details"] = device_details
                    zone_data["device_profile"] = device_profile

                site_data["zones"].append(zone_data)

            result["sites"].append(site_data)

    return result


async def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python get_devices.py <username> <password>", file=sys.stderr)
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    try:
        result = await fetch_all_devices(username, password)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())