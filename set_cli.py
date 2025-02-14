#!/usr/bin/env python3

import yaml
import click
import os
import requests
import tempfile
import shutil
import gnupg

from utils import *

import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="tarfile")

cellar = "/home/group/public/894cf/cellar"
root = "/home/group/public/894cf/.root"


class RecipeObserver:
    def cant_download(self, url: str):
        pass


class ClickRecipeObserver(RecipeObserver):
    def cant_download(self, url):
        click.echo(f"Cannot download ${click.style(url, fg='red')}")


class Observable:
    def __init__(self):
        self.observers : List[RecipeObserver] = []
    
    def add_observer(self, observer: RecipeObserver):
        self.observers.append(observer)

    def notify(self, message):
        for observer in self.objservers:
            observer.notify(message)
    

def validate_dict(contents: dict, mandatory_fields: List[str], context=""):
    for field in mandatory_fields:
        if field not in contents:
            raise Exception(f"Missing '{field}' ({context})")
    

def validate_recipe(recipe: dict):
    validate_dict(recipe, ["package", "download", "build"], context = "recipe")
        
def validate_package(package: dict):
    validate_dict(package, ["name", "version"], context = "package")
    
def validate_build(build: dict):
    validate_dict(build, ["steps"], context="build")

def validate_download(download: dict):
    if "url" not in download and "github" not in download:
        raise Exception("Invalid download specs, check your recipe")
    

class Package:
    def __init__(self, package):
        validate_package(package)
        self.package = package
        self.name = package["name"]
        self.version = package["version"]
        self.slug = f"{self.name}@{self.version}"
        self.relative_path = f"{self.name}/{self.version}"

class URLDownload:
    def __init__(self, download: dict, workdir: str):
        if "url" not in download:
            raise Exception("don't know that to download here")
        self.url = download["url"]
        self.workdir = workdir
        self.download = download
        
    def verify(self):
        if "verify" not in self.download:
            return
        
        if not hasattr(self, "filepath"):
            raise Exception("Cannot verify something I've not downloaded")
        
        verified = False
        if "sign" in self.download["verify"]:
            sign_url = self.download["verify"]["sign"]
            sign_path = download_file(sign_url, self.workdir)
            gpg = gnupg.GPG()

            # Carica la tua chiave pubblica (se non l'hai già importata)
            # gpg.import_keys(open('your_public_key.asc').read())

            # Verifica la firma
            with open(sign_path, 'rb') as sig_file, open(self.filepath, 'rb') as tarball_file:
                verified = gpg.verify_file(sig_file, tarball_file)

        elif "sha512" in self.download["verify"]:
            expected = self.download["verify"]["sha512"]
            computed_hash = calcola_sha512(self.filepath)
            verified = computed_hash == expected
            
        if not verified:
            raise Exception("File is not verified, check your sources")
        
    def decompress(self):
        """Decompress the packaged downloaded and returns the directory"""
        if not hasattr(self, "filepath"):
            raise Exception("Cannot verify something I've not downloaded")
        
        decompress_file(self.filepath, self.workdir)
        directories = list_directories(self.workdir)
        if len(directories) == 1:
            return f"{self.workdir}/{directories[0]}"
        else:
            return self.workdir
        
    def __call__(self):
        """
        Downloads, verify and decompress the package.
        Returns the directory decompressed
        """
        self.filepath = download_file(self.url, self.workdir)
        self.verify()
        return self.decompress()


class GithubDownload:
    pass



class Build(Observable):
    def __init__(self, build, install_dir):
        validate_build(build)
        self.build = build
        self.install_dir = install_dir
        if "steps" not in build:
            raise Exception("There are no steps to execute")
        
        self.steps = build["steps"]
        
    def notify(self, message):
        for observer in self.objservers:
            observer.notify(message)
            
    def __call__(self, build_dir):
        for step in self.steps:
            rc = run_command(step.format(prefix=self.install_dir), cwd=build_dir)
            if (rc != 0):
                self.notify(f"{step} has returned non-zero value ({rc}), please check logs")


class Recipe(Observable):
    """
    Recipe Class: downloads, decompress, build a recipe
    """

    def __init__(self, recipe: dict, cellar: str = cellar):
        validate_recipe(recipe)
        self.recipe = recipe
        self.workdir = tempfile.mkdtemp()
        
        download = recipe["download"]
        if "url" in download:
            self.download = URLDownload(download, self.workdir)
        if "github" in recipe["download"]:
            self.download = GithubDownload(download, self.workdir)
            
        self.package = Package(recipe["package"])
        install_dir = f"{cellar}/{self.package.relative_path}"
        self.build = Build(recipe["build"], install_dir)
        
        
    def __call__(self):
        self.build_dir = self.download()
        self.build(self.build_dir)
        
    def done(self):
        shutil.rmtree(self.workdir)

    

class LinkableRecipe(Recipe):
    def link(self, source: str, dest: str = root):
        """
        Links a package installed in `source` into main root `dest`
        """
        partial_dirs, partial_source_files = collect_files(source)

        files = [f"{source}/{file}" for file in partial_source_files]
        dest_files = ["f{dest}/{file}" for file in partial_source_files]

        simlinks_mapping = zip(files, dest_files)

        dirs = [f"{dest}/{dir}" for dir in partial_dirs]

        # make sure they exists (those should be bin, lib, share, include, etc...)
        (os.makedirs(dir) for dir in dirs if not os.path.exists(dir))

        for source_file, dest_file in simlinks_mapping:
            if os.path.exists(dest_file):
                click.echo(f"{dest_file} exits!")
                if not os.path.islink(dest_file):
                    click.echo(
                        f"... and {dest_file} is not a symlink, check your install"
                    )
                click.echo(
                    f"Remove file, (don't worry, it will be relinked now)"
                )
                os.remove(dest_file)

            click.echo(f"Creating symlink {source_file} -> {dest_file}")
            os.simlink(source_file, dest_file)

    def unlink(self, source, dest=root):
        _, partial_source_files = collect_files(source)

        dest_files = ["f{dest}/{file}" for file in partial_source_files]

        for file in dest_files:
            click.echo(f"Removing {file}")
            if os.path.exists(file):
                os.remove(file)

@click.group()
def cli():
    pass


def recipe_factory(package_name: str) -> Recipe:
    if os.path.isfile(package_name):
        with open(package_name, "r") as f:
            recipe_content = f.read()

    else:
        repo_url = "http://osiride-public.utenze.bankit.it/~m024000/Set"
        url = f"{repo_url}/{package_name}"

        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Package not Found")

        recipe_content = response.text

    recipe = yaml.load(recipe_content, Loader=yaml.FullLoader)
    return Recipe(recipe)


@click.command()
@click.argument("package_name")
def install(package_name: str):
    """Installs a package"""
    click.echo(f"Installing {click.style(package_name, fg='green')}")

    recipe = recipe_factory(package_name)
    recipe()


@click.command()
@click.argument("package_name")
def link(package_name: str):
    """
  Links a package. if not installed, provides to install.
  """
    click.echo(f"Linking.. {click.style(package_name, fg='green')}")
    recipe = recipe_factory(package_name)
    if not recipe.is_installed():
        recipe()

    recipe.link(recipe.install_dir())


@click.command()
@click.argument("package_name")
def unlink(package_name: str):
    """
  Unlinks a package. if not installed, does nothing.
  """
    click.echo(f"Unlinking {click.style(package_name, fg='green')}")
    recipe = recipe_factory(package_name)
    if not recipe.is_installed():
        return

    recipe.unlink()


@click.command()
@click.argument("package_name")
def uninstall(package_name: str):
    """
  Uninstalls a package. if not installed, does nothing.
  """
    click.echo(f"Removing {click.style(package_name, fg='green')}")
    recipe = recipe_factory(package_name)
    if not recipe.is_installed():
        return

    recipe.unlink()
    recipe.uninstall()


cli.add_command(install)
cli.add_command(link)
cli.add_command(unlink)
cli.add_command(uninstall)

if __name__ == "__main__":
    cli()
