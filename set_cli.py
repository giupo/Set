#!/usr/bin/env python3

import toml
import click
import os
import requests
import tempfile
import shutil
import subprocess

from utils import *
from tqdm import tqdm
from urllib.parse import urlsplit
from typing import Tuple

# config = toml.load("Set.toml")

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


class Recipe:
    """
  Base Recipe Class, used just for reference.
  """

    def __init__(self):
        self.workdir = tempfile.mkdtemp()

    def done(self):
        click.echo(f"Removing Workdir: {click.style(self.workdir, fg='blue')}")
        shutil.rmtree(self.workdir)

    def configure():
        pass

    def build():
        pass

    def install():
        pass


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


class MakefileRecipe(LinkableRecipe):
    def __init__(self, recipe: dict):
        if "package" not in recipe:
            raise "No Package definition"
        package = recipe["package"]

        if "name" not in package:
            raise "No Name specified"
        if "version" not in package:
            raise "No Version specified"
        if "url" not in package:
            raise "No URL specified"

        self.name = package["name"]
        self.version = package["version"]
        self.url = package["url"]
        self.recipe = recipe

        self.workdir = tempfile.mkdtemp()
        self.slug = f"{self.name}@{self.version}"
        click.echo(f"Workdir: {click.style(self.workdir, fg='blue')}")

    def configure(self, package_dir, root=cellar):
        if "configure" not in self.recipe:
            return

        recipe = self.recipe["configure"]

        if "dir" in recipe:
            build_dir_name = recipe["dir"]
            build_dir = f"{package_dir}/{build_dir_name}"
            if os.path.exists(build_dir):
                raise Exception("Build dir exist, change dir config in recipe")
            os.makedirs(build_dir)

        else:
            build_dir = package_dir

        if "args" in recipe:
            args = recipe["args"]
        else:
            args = ""

        if "cmd" in recipe:
            command = recipe["cmd"]
            command = f"{command} --prefix={self.install_dir(root)}"
        else:
            command = f"./configure --prefix={self.install_dir(root)} {args}"

        run_command(command, cwd=build_dir)
        return build_dir

    def install_dir(self, root=cellar):
        return f"{root}/{self.name}/{self.version}"

    def build(self, build_dir):
        click.echo("Package_dir: {build_dir}")
        if "build" not in self.recipe:
            return

        recipe = self.recipe["build"]

        if "args" in recipe:
            args = recipe["args"]
        else:
            args = ""

        command = f"make -j {args}"
        run_command(command, cwd=build_dir)

        return build_dir

    def has(self, key: str) -> bool:
        return key in self.recipe

    def download(self):
        response = requests.get(self.url, stream=True)
        filename = os.path.basename(urlsplit(self.url).path)
        filepath = os.path.join(self.workdir, filename)
        if response.status_code != 200:
            self.notify_cant_download(self.url)
            raise

        total_size = int(response.headers.get("content-length", 0))

        with open(filepath, "wb") as file:
            for chunk in tqdm(
                response.iter_content(chunk_size=1024),
                total=total_size // 1024,  # Calcola il totale in MB
                unit="KB",
                desc=click.style(self.slug, fg="blue"),
            ):
                if chunk:
                    file.write(chunk)  # Scrive ogni blocco nel file

        return filepath

    def decompress(self, filepath):
        decompress_file(filepath, self.workdir)
        directories = list_directories(self.workdir)
        if len(directories) == 1:
            return f"{self.workdir}/{directories[0]}"
        else:
            return self.workdir

    def install(self, build_dir, root=cellar):
        if "install" not in self.recipe:
            return

        recipe = self.recipe["install"]

        if "args" in recipe:
            args = recipe["args"]
        else:
            args = ""

        command = f"make -j {args}"
        dest = self.install_dir(root=root)
        click.echo(f"Installing {click.style(self.slug, fg='blue')} to {dest}")
        rc = run_command(command, cwd=build_dir)
        if rc != 0:
            click.echo(f"build didn't return zero (rc: {rc}), check logs")
        click.echo(f"Installed {click.style(self.slug, fg='blue')} to {dest}")
        return dest

    def __call__(self, root=root):
        """
    Execute the recipe:
    - download and decompress
    - configure the package (if needed)
    - build the package (if needed)
    - install the package (if needed)
    
    and returns the install_dir in the cellar.
    """
        package_dir = self.decompress(self.download())
        build_dir = self.configure(package_dir)
        build_dir = self.build(build_dir)
        install_dir = self.install(build_dir)
        self.done()

        return install_dir

    def uninstall(self, root=cellar):
        shutil.rmtree(self.install_dir(root=root))

    def is_installed(self, root=cellar):
        dir = self.install_dir(root=cellar)
        return os.path.isdir(dir) and bool(os.listdir(dir))


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

    recipe = toml.loads(recipe_content)
    return MakefileRecipe(recipe)


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
