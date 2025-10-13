from fastapi import APIRouter, HTTPException, Body
import psutil
import platform
from datetime import datetime

from app.models.schemas import DiskData, SystemNetworkStatus, SystemStatus

router = APIRouter(prefix="/system", tags=["System"])

def get_size(bytes, suffix="B"):
    """
    Scale bytes to its proper format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor

@router.get("/status", response_model=SystemStatus)
async def get_all_system_info():
    """
    Get all system information.
    
    Returns
    -------
        SystemStatus
    """
    uname = platform.uname()
    
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.fromtimestamp(boot_time_timestamp)
    uptime = datetime.now() - bt
    
    cpufreq = psutil.cpu_freq()
    svmem = psutil.virtual_memory()
    partitions = psutil.disk_partitions()
    
    disks_data = []
    for partition in partitions:
        try:
            partition_usage = psutil.disk_usage(partition.mountpoint)
            
            disk_data = DiskData(
                device=partition.device,
                mountpoint=partition.mountpoint,
                fstype=partition.fstype,
                total=get_size(partition_usage.total),
                used=get_size(partition_usage.used),
                free=get_size(partition_usage.free),
                percent=partition_usage.percent
            )
        except PermissionError:
            # this can be catched due to the disk that isn't ready
            disk_data = DiskData(
                device=partition.device,
                mountpoint=partition.mountpoint,
                fstype=partition.fstype,
                total=None,
                used=None,
                free=None,
                percent=None
            )
        disks_data.append(disk_data)
    
    network_interfaces = []
    if_addrs = psutil.net_if_addrs()
    for interface_name, interface_addresses in if_addrs.items():
        for address in interface_addresses:
            if str(address.family) == 'AddressFamily.AF_INET':
                network_interfaces.append(SystemNetworkStatus(
                    name=interface_name,
                    family=str(address.family),
                    ip_address=address.address,
                    mac_address=None,
                    subnet_mask=address.netmask,
                    broadcast=address.broadcast
                ))
            elif str(address.family) == 'AddressFamily.AF_PACKET':
                network_interfaces.append(SystemNetworkStatus(
                    name=interface_name,
                    family=str(address.family),
                    ip_address=None,
                    mac_address=address.address,
                    subnet_mask=address.netmask,
                    broadcast=address.broadcast
                ))
    
    net_io = psutil.net_io_counters()
    
    return SystemStatus(
        system=uname.system,
        node_name=uname.node,
        version=uname.version,
        machine=uname.machine,
        processor=uname.processor,
        boot_time=f"{bt.year}/{bt.month}/{bt.day} {bt.hour}:{bt.minute}:{bt.second}",
        uptime=f"{uptime.days} days, {uptime.seconds // 3600} hours",
        cpu_physical_cores=psutil.cpu_count(logical=False),
        cpu_logical_cores=psutil.cpu_count(logical=True),
        cpu_max_frequency=cpufreq.max,
        cpu_current_frequency=round(cpufreq.current, 3),
        cpu_usage=psutil.cpu_percent(),
        memory_total=get_size(svmem.total),
        memory_available=get_size(svmem.available),
        memory_used=get_size(svmem.used),
        memory_usage=svmem.percent,
        disks=disks_data,
        network_interfaces=network_interfaces,
        network_sent=get_size(net_io.bytes_sent),
        network_received=get_size(net_io.bytes_recv),
        cpu_temperature=psutil.sensors_temperatures(fahrenheit=False)
    )

@router.get("/cpu_usage")
async def get_cpu_usage():
    # Implement CPU usage function
    return {"cpu_usage_percent": 25}

@router.get("/memory_usage")
async def get_memory_usage():
    # Implement memory usage function
    return {"memory_usage_percent": 50}

@router.get("/disk_usage")
async def get_disk_usage():
    # Implement disk usage function
    return {"disk_usage_percent": 75}

@router.get("/network_speed")
async def get_network_speed():
    # Implement network speed function
    return {"network_speed_mbps": 100}

@router.get("/network_type")
async def get_network_type():
    # Implement network type function
    return {"network_type": "Ethernet"}

@router.get("/cpu_temperature")
async def get_cpu_temperature():
    # Implement CPU temperature function
    return {"cpu_temperature_degrees_c": 45}

@router.get("/uptime")
async def get_uptime():
    # Implement uptime function
    return {"uptime_mins": 1710}

if __name__ == "__main__":
    print(get_all_system_info())