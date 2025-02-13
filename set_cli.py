#!/usr/bin/env python3

import toml
import click
import os
import requests
import tempfile
import shutil
import subprocess

# decompress algos
import zipfile
import tarfile
import gzip
import bz2
import lzma

from tqdm import tqdm
from urllib.parse import urlsplit
# config = toml.load("Set.toml")

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="tarfile")

class Recipe:
  def __init__(self, recipe: dict)
    if "name" not in recipe:
      raise
    if "version" not in recipe
      raise
    
    self.name = recipe["name"]
    self.version = recipe["version"]
    self.recipe = recipe
    
  @property
  def install_dir(self, root = "/home/group/public/894cf/cellar"):
    return f"{root}/{self.name}/{self.version}"

  @property
  def configure():
    if "configure" not in self.recipe:
      raise "Configure doesn't exist"
    return self.recipe["configure"]

  def has(key: str) -> bool:
    return key in self.recipe
  
@click.group()
def cli():
  pass

def download_package(package_url: str, workdir: str):
  response = requests.get(package_url, stream=True)

  filename = os.path.basename(urlsplit(package_url).path)
  filepath = os.path.join(workdir, filename)
  if response.status_code != 200:
    click.echo(f"Cannot download ${click.style(package_url, fg='red')}")
    raise
  
  total_size = int(response.headers.get('content-length', 0))
    
  with open(filepath, "wb") as file:
    for chunk in tqdm(response.iter_content(chunk_size=1024), 
      total=total_size // 1024,  # Calcola il totale in MB
      unit='KB', desc=click.style("Scaricando", fg="blue")):
      if chunk:  
        file.write(chunk)  # Scrive ogni blocco nel file

  return filepath

def get_package_install_dir(recipe: dict) -> str:
  package = recipe["package"] if "package" in recipe else None
  name = package["name"] if "name" in package else None
  version = package["version"] if "version" in package else None
  
  if package or name or version is None:
    raise "invalid recipe"
  
  return f"{cellar}/{name}/{version}"

def get_package_dir(workdir: str) -> str:
  """
  ritorna la directory del package dopo averlo decompresso
  
  Alcuni packags non hanno subdirectory, quindi se dentro workdir c'e' una sola directory
  e' molto probabile che siq la packagedir
  """
  listdir = os.listdir(workdir)
  if len(listdir) == 1:
    return listdir[0]
  return workdir

def run_command(command, cwd=None):
  """Esegue un comando nel sistema e gestisce eventuali errori."""
  try:
    # Esegui il comando come un processo separato
    result = subprocess.run(command, shell=True, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    click.echo(result.stdout.decode())  # Mostra l'output standard
    return result
  except subprocess.CalledProcessError as e:
    click.echo(f"Errore durante l'esecuzione del comando: {e}")
    click.echo(f"Stderr: {e.stderr.decode()}")
    raise  # Rilancia l'eccezione per terminare l'esecuzione


def decompress_file(input_file, output_dir):
  if not os.path.exists(output_dir):
    os.makedirs(output_dir)

  try:
    # Try ZIP file
    if input_file.endswith('.zip'):
      with zipfile.ZipFile(input_file, 'r') as zip_ref:
        zip_ref.extractall(output_dir)
      click.echo(f"Decompressed ZIP file to {click.style(output_dir, fg='green')}")

    # Try TAR file
    elif input_file.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz')):
      with tarfile.open(input_file, 'r') as tar_ref:
        tar_ref.extractall(output_dir)
      click.echo(f"Decompressed TAR file to {click.style(output_dir, fg='green')}")
      

    # Try GZ file
    elif input_file.endswith('.gz'):
      with gzip.open(input_file, 'rb') as gz_ref:
        with open(os.path.join(output_dir, os.path.basename(input_file).replace('.gz', '')), 'wb') as out_file:
          out_file.write(gz_ref.read())
      click.echo(f"Decompressed GZ file to {click.style(output_dir, fg='green')}")
      
    # Try BZ2 file
    elif input_file.endswith('.bz2'):
      with bz2.open(input_file, 'rb') as bz2_ref:
        with open(os.path.join(output_dir, os.path.basename(input_file).replace('.bz2', '')), 'wb') as out_file:
          out_file.write(bz2_ref.read())
      click.echo(f"Decompressed BZ2 file to {click.style(output_dir, fg='green')}")
     
    # Try XZ file
    elif input_file.endswith('.xz'):
      with lzma.open(input_file, 'rb') as xz_ref:
        with open(os.path.join(output_dir, os.path.basename(input_file).replace('.xz', '')), 'wb') as out_file:
          out_file.write(xz_ref.read())
      click.echo(f"Decompressed XZ file to {click.style(output_dir, fg='green')}")
      
    else:
      click.echo(f"Unsupported file type for {click.style(input_file, fg='red')}")
    
  except Exception as e:
    click.echo(click.style(f"Error during decompression: {e}", fg="red"))

def get_recipe(package_name: str) -> Recipe:
  if os.path.isfile(package_name):
    with open(package_name, "r") as f:
      recipe_content = f.read()
  
  else:
    repo_url = "http://osiride-public.utenze.bankit.it/~m024000/Set"
    url = f"{repo_url}/{package_name}"
    
    response = requests.get(url)
    if response.status_code != 200:
      raise "Pacchetto insesitente" 

    recipe_content = response.text

  recipe = toml.loads(recipe_content)
  return recipe

def build_install(package_dir, recipe: Recipe, root = "oh god, define me!"):
  build_dir = os.path.join(package_dir, "build")
  os.makedirs(build_dir)
  
  if 'configure' in recipe:
    configure = recipe['configure']
  
  if 'build' in recipe:
    build = recipe['build']
    
  if 'install' in recipe:
    install_dir = get_package_install_dir(recipe)
    
    
  run_command(f"../configure --prefix={root}", cwd=build_dir)
  run_command("make -j", cwd=build_dir)
  # run_command("make install")


@click.command()
@click.argument('package_name')
def install(package_name: str):
  click.echo(f"Installing {click.style(package_name, fg='green')}")

  workdir = tempfile.mkdtemp()
  click.echo(f"Workdir: {click.style(workdir, fg='blue')}")
  
  recipe = get_recipe(package_name)
  
  package_url = recipe["package"]["url"]
  filepath = download_package(recipe["package"]["url"], workdir)
  decompress_file(filepath, workdir)
  package_dir = get_package_dir(workdir)
  build_dir = os.path.join(package_dir, "build")

  build_install(package_dir, recipe)
  # run_command("make install")
  click.echo(f"Removing Workdir: {click.style(workdir, fg='blue')}")
  shutil.rmtree(workdir)
  
  # make temp directory where working
  

cli.add_command(install)

if __name__ == "__main__":
  cli()