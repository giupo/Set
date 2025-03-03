# -*- coding:utf-8 -*-
import yaml

from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field

class Build(BaseModel):
  steps: List[str]


class Download(BaseModel):
  url: HttpUrl = Field(..., description="Must be a valid URL")


class GithubDownload(Download):
  tag: str = "main"


class Version(BaseModel):
  version: str
  download: Download
  build: Optional[Build] = None
  

class Package(BaseModel):
  name: str
  versions: List[Version]
  build: Optional[Build] = None
  download: Optional[Download] = None
  

def package_factory(path: str) -> Package:
  """Build a Package class from the YAML file contents"""
  
  # Parse the YAML file
  with open(path, "r") as yaml_file:
    data = yaml.load(yaml_file, Loader=yaml.FullLoader)
  
  package_contents = data['package']
  
  # Create a new Version object for each version
  versions = []
  for version in package_contents['versions']:   
    download_contents = version['download'] 
    if 'tag' in download_contents:
      download = GithubDownload(**download_contents)
    else:
      download = Download(**download_contents)
    
    if 'build' in version:
      build_contents = version['build']
      build = Build(**build_contents)
      versions.append(
        Version(
          version=version['version'], 
          download=download, 
          build=build
        )
      )
    
  # Add the package build and download information
  build = None
  if 'build' in data:
    build = Build(**data['build'])

  download = None
  if 'download' in data:
    download = Download(**data['download'])
    
  return Package(
    name=package_contents['name'],
    versions=versions,  
    build=build
  )