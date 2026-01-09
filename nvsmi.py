#!/usr/bin/env python3

'''
This script highly depends on Python reflection, DO NOT use `from __future__ import annotations` which turns typing objects to type name strings thus breaking reflection-related codes!!
'''

import re
import json
import subprocess
from copy import deepcopy
from argparse import ArgumentParser
from typing import List, Dict, Literal, Callable, Union, Any

__all__ = [
  'NVSMI',
  'NVSMI_Entry',
  'NVSMI_Static',
  'NVSMI_Dynamic',
]

T_type = type(type)


def regex_find(template: str, pattern: str) -> str:
  match = re.search(pattern, template)
  if not match: return ''
  return match.group(0)

def str_to_num(s: str) -> Union[int, float]:
  try:
    fval = float(s)
    ival = int(fval)
    return ival if fval == ival else fval
  except:
    return -1

def lines_find_line(lines: List[str], title: str) -> str:
  for line in lines:
    if title in line:
      return line
  return ''

def lines_find_section(lines: List[str], title: str) -> List[str]:
  section: List[str] = []
  found, indent = False, -1
  count_leading_spaces: Callable[[str], int] = lambda line: len(line) - len(line.lstrip(' '))
  for line in lines:
    if title == line.strip():
      found = True
      indent = count_leading_spaces(line)
      section.append(line)
      continue
    if found:
      if count_leading_spaces(line) > indent:
        section.append(line)
      else:
        break   # only match the first section
  return section

def run_cmd(cmd_args: List[str]) -> List[str]:
  executable = cmd_args[0]
  try:
    p = subprocess.run(cmd_args, capture_output=True, text=True, check=True)
  except FileNotFoundError:
    raise RuntimeError(f"{executable} not found in PATH")
  except subprocess.CalledProcessError as e:
    raise RuntimeError(f"{executable} failed: {e}")
  return p.stdout.strip().split('\n')

def merge_object_attrs(objA: object, objB: object):
  ''' deep copy and merge attrs objA <- objB '''
  for name, value in vars(objB).items():
    if name not in objA:
      objA[name] = deepcopy(value)
    else:
      merge_object_attrs(objA[name], deepcopy(value))
  return objA


class DMixin:

  def __contains__(self, name: str) -> bool:
    return hasattr(self, name)

  def __getitem__(self, name: str) -> Any:
    return getattr(self, name, None)

  def __setitem__(self, name: str, value: Any):
    setattr(self, name, value)

class IMixin:

  def from_line(vtype: type, line: str) -> Union[str, int, float]:
    p = line.find(':')
    if p < 0: return 'N/A'
    val_s = line[p + 1:].strip()
    if vtype in (int, float):
      val_s = regex_find(val_s, r'[\d\.]+')   # extract numerical part
      return str_to_num(val_s)
    else:
      return val_s

  @classmethod
  def from_lines(cls, lines: List[str]):
    obj = cls()
    for name, vtype in obj.__annotations__.items():
      title = name.replace('_', ' ')
      if type(vtype) == T_type and issubclass(vtype, IOMixin):
        section = lines_find_section(lines, title)
        obj[name] = vtype.from_lines(section)
      else:
        line = lines_find_line(lines, title)
        obj[name] = cls.from_line(vtype, line)
    return obj

class OMixin:

  def to_dict(self) -> Dict[str, Any]:
    data = {}
    for name, vtype in self.__annotations__.items():
      if name in data: continue
      value = self[name]
      if value == 'N/A': continue
      title = name.replace('_', ' ')
      if type(vtype) == T_type and issubclass(vtype, OMixin):
        data[title] = value.to_dict()
      else:
        data[title] = value
    return data

  def __dict__(self):
    return self.to_dict()

  def __repr__(self):
    return json.dumps(self.to_dict(), indent=2)

  def __str__(self):
    return str(self.to_dict())

class IOMixin(IMixin, OMixin, DMixin):
  pass

class NVSMI_Entry(OMixin, DMixin):

  device_id: int
  model: str
  uuid: str

  def __init__(self, **kwargs):
    for name, value in kwargs.items():
      if name in self.__annotations__:
        self[name] = value

class NVSMI_Static(IOMixin):
  class NVSMI_PCI(IOMixin):
    class NVSMI_GPU_Link_Info(IOMixin):
      class NVSMI_PCIe_Generation(IOMixin):
        Max                  : int
        Device_Max           : int
      class NVSMI_Link_Width(IOMixin):
        Max                  : str # '16x'

      PCIe_Generation        : NVSMI_PCIe_Generation
      Link_Width             : NVSMI_Link_Width

    Bus                      : str
    Device                   : str
    Domain                   : str
    Device_Id                : str
    Bus_Id                   : str
    Sub_System_Id            : str
    GPU_Link_Info            : NVSMI_GPU_Link_Info
  class NVSMI_FB_Memory_Usage(IOMixin):
    Total                    : int # MiB
  class NVSMI_BAR1_Memory_Usage(IOMixin):
    Total                    : int # MiB
  class NVSMI_Temperature(IOMixin):
    GPU_Shutdown_Temp        : int # °C
    GPU_Slowdown_Temp        : int # °C
    GPU_Max_Operating_Temp   : int # °C
    GPU_Target_Temperature   : int # °C
  class NVSMI_GPU_Power_Readings(IOMixin):
    Default_Power_Limit      : float # W
    Min_Power_Limit          : float # W
    Max_Power_Limit          : float # W
  class NVSMI_Max_Clocks(IOMixin):
    Graphics                 : int # MHz
    SM                       : int # MHz
    Memory                   : int # MHz
    Video                    : int # MHz

  Product_Name               : str
  Product_Brand              : str
  Product_Architecture       : str
  GPU_UUID                   : str
  GPU_PDI                    : str
  VBIOS_Version              : str
  MultiGPU_Board             : Union[Literal['Yes'], Literal['No']]
  Board_ID                   : str
  GPU_Part_Number            : str
  PCI                        : NVSMI_PCI
  FB_Memory_Usage            : NVSMI_FB_Memory_Usage
  BAR1_Memory_Usage          : NVSMI_BAR1_Memory_Usage
  Temperature                : NVSMI_Temperature
  GPU_Power_Readings         : NVSMI_GPU_Power_Readings
  Max_Clocks                 : NVSMI_Max_Clocks

class NVSMI_Dynamic(IOMixin):
  class NVSMI_Driver_Model(IOMixin):
    Current: Union[Literal['WDDM'], Literal['TCC']]
    Pending: Union[Literal['WDDM'], Literal['TCC']]
  class NVSMI_PCI(IOMixin):
    class NVSMI_GPU_Link_Info(IOMixin):
      class NVSMI_PCIe_Generation(IOMixin):
        Current              : int
        Device_Current       : int
        Host_Max             : int
      class NVSMI_Link_Width(IOMixin):
        Current              : str # '16x'

      PCIe_Generation        : NVSMI_PCIe_Generation
      Link_Width             : NVSMI_Link_Width

    GPU_Link_Info            : NVSMI_GPU_Link_Info
    Tx_Throughput            : int # KB/s
    Rx_Throughput            : int # KB/s
  class NVSMI_FB_Memory_Usage(IOMixin):
    Reserved                 : int # MiB
    Used                     : int # MiB
    Free                     : int # MiB
  class NVSMI_BAR1_Memory_Usage(IOMixin):
    Used                     : int # MiB
    Free                     : int # MiB
  class NVSMI_Utilization(IOMixin):
    GPU                      : int # percent
    Memory                   : int # percent
    Encoder                  : int # percent
    Decoder                  : int # percent
    JPEG                     : int # percent
    OFA                      : int # percent
  class NVSMI_Temperature(IOMixin):
    GPU_Current_Temp         : int # °C
  class NVSMI_GPU_Power_Readings(IOMixin):
    Current_Power_Limit      : float # W
    Requested_Power_Limit    : float # W
    Average_Power_Draw       : float # W
    Instantaneous_Power_Draw : float # W
  class NVSMI_Clocks(IOMixin):
    Graphics                 : int # MHz
    SM                       : int # MHz
    Memory                   : int # MHz
    Video                    : int # MHz

  Timestamp                  : str # datetime string
  Driver_Version             : str # 'xxx.xx'
  CUDA_Version               : str # 'xx.x'
  Display_Attached           : Union[Literal['Yes'], Literal['No']]
  Display_Active             : Union[Literal['Enabled'], Literal['Disabled']]
  Driver_Model               : NVSMI_Driver_Model
  PCI                        : NVSMI_PCI
  Fan_Speed                  : int # percent
  Performance_State          : str # 'P8'
  FB_Memory_Usage            : NVSMI_FB_Memory_Usage
  BAR1_Memory_Usage          : NVSMI_BAR1_Memory_Usage
  Utilization                : NVSMI_Utilization
  Temperature                : NVSMI_Temperature
  GPU_Power_Readings         : NVSMI_GPU_Power_Readings
  Clocks                     : NVSMI_Clocks

class NVSMI(OMixin, DMixin):

  def __init__(self, device_id: int = 0):
    assert isinstance(device_id, int) and device_id >= 0, 'device_id must be an integer'
    self.device_id = device_id

    # raw info string
    lines = run_cmd(['nvidia-smi', '-q', '-i', str(device_id)])
    # parsed struct
    self.nvs = NVSMI_Static.from_lines(lines)
    self.nvd = NVSMI_Dynamic.from_lines(lines)
    # hijack: mount all attrs on this `self`
    self.__annotations__ = {}
    self.__annotations__.update(self.nvs.__annotations__)
    self.__annotations__.update(self.nvd.__annotations__)
    merge_object_attrs(self, self.nvs)
    merge_object_attrs(self, self.nvd)

  @staticmethod
  def list_gpus():
    lines = run_cmd(['nvidia-smi', '-L'])

    REGEX_GPU_ENTRY = re.compile(r'GPU\s+(\d+):\s+([^(]+)\s+\(UUID:\s+([\w\-]+)\)')
    gpu_list: List[NVSMI_Entry] = []
    for line in lines:
      m = REGEX_GPU_ENTRY.search(line)
      if not m: continue
      device_id, model, uuid = m.groups()
      gpu_list.append(NVSMI_Entry(device_id=int(device_id), model=model, uuid=uuid))
    return gpu_list

  @classmethod
  def query_gpu(cls, device_id: int = 0):
    return cls(device_id)

  @property
  def brief(self) -> str:
    return ' '.join([
      f'[{self.device_id}]',
      f'Name: {self.nvs.Product_Name},',
      f'Power: {self.nvd.GPU_Power_Readings.Average_Power_Draw}W,',
      f'Temp: {self.nvd.Temperature.GPU_Current_Temp}°C,',
      f'Fan: {self.nvd.Fan_Speed}%,',
      f'Usage: {self.nvd.Utilization.GPU}%',
    ])


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('-L', '--list_gpus', action='store_true', help='list devices')
  parser.add_argument('-i', '--device_id', type=int, default=-1, help='gpu device id')
  parser.add_argument('-B', '--brief', action='store_true', help='show brief info one-line')
  parser.add_argument('-S', '--static', action='store_true', help='show static info tree')
  parser.add_argument('-D', '--dynamic', action='store_true', help='show dynamic info tree')
  args = parser.parse_args()

  if args.list_gpus:
    entries = NVSMI.list_gpus()
    print(entries)
  else:
    if args.brief:
      if args.device_id < 0:
        entries = NVSMI.list_gpus()
        for entry in entries:
          nvsmi = NVSMI.query_gpu(entry.device_id)
          print(nvsmi.brief)
      else:
        nvsmi = NVSMI.query_gpu(args.device_id)
        print(nvsmi.brief)
    else:
      if args.device_id < 0:
        entries = NVSMI.list_gpus()
        if entries:
          device_id = entries[0].device_id
          if len(entries) > 1:
            print(f'>> WARN: option -i <device_id> not specified, defaults to GPU-{device_id}')
          args.device_id = device_id
        else:
          raise OSError('no GPU device found')

      from pprint import pprint

      nvsmi = NVSMI.query_gpu(args.device_id)
      if not args.static and not args.dynamic:
        pprint(nvsmi)
      if args.static:
        pprint(nvsmi.nvs)
      if args.dynamic:
        pprint(nvsmi.nvd)
