import click
import os

# decompress algos
import zipfile
import tarfile
import gzip
import bz2
import lzma
import subprocess

from typing import List, Tuple


def run_command(command, cwd=None):
    """Esegue un comando nel sistema e gestisce eventuali errori."""
    try:
        # Esegui il comando come un processo separato
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            click.echo(line.strip())  # Stampa senza newline extra

        return process.wait()
    except subprocess.CalledProcessError as e:
        click.echo(f"Errore durante l'esecuzione del comando: {e}")
        click.echo(f"Stderr: {e.stderr.decode()}")
        raise  # Rilancia l'eccezione per terminare l'esecuzione


def decompress_file(input_file, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # Try ZIP file
        if input_file.endswith(".zip"):
            with zipfile.ZipFile(input_file, "r") as zip_ref:
                zip_ref.extractall(output_dir)
            click.echo(
                f"Decompressed ZIP file to {click.style(output_dir, fg='green')}"
            )

        # Try TAR file
        elif input_file.endswith(
            (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")
        ):
            with tarfile.open(input_file, "r") as tar_ref:
                tar_ref.extractall(output_dir)
            click.echo(
                f"Decompressed TAR file to {click.style(output_dir, fg='green')}"
            )

        # Try GZ file
        elif input_file.endswith(".gz"):
            with gzip.open(input_file, "rb") as gz_ref:
                with open(
                    os.path.join(
                        output_dir,
                        os.path.basename(input_file).replace(".gz", ""),
                    ),
                    "wb",
                ) as out_file:
                    out_file.write(gz_ref.read())
            click.echo(
                f"Decompressed GZ file to {click.style(output_dir, fg='green')}"
            )

        # Try BZ2 file
        elif input_file.endswith(".bz2"):
            with bz2.open(input_file, "rb") as bz2_ref:
                with open(
                    os.path.join(
                        output_dir,
                        os.path.basename(input_file).replace(".bz2", ""),
                    ),
                    "wb",
                ) as out_file:
                    out_file.write(bz2_ref.read())
            click.echo(
                f"Decompressed BZ2 file to {click.style(output_dir, fg='green')}"
            )

        # Try XZ file
        elif input_file.endswith(".xz"):
            with lzma.open(input_file, "rb") as xz_ref:
                with open(
                    os.path.join(
                        output_dir,
                        os.path.basename(input_file).replace(".xz", ""),
                    ),
                    "wb",
                ) as out_file:
                    out_file.write(xz_ref.read())
            click.echo(
                f"Decompressed XZ file to {click.style(output_dir, fg='green')}"
            )

        else:
            click.echo(
                f"Unsupported file type for {click.style(input_file, fg='red')}"
            )

    except Exception as e:
        click.echo(click.style(f"Error during decompression: {e}", fg="red"))
        raise e


def list_directories(dir: str) -> None | List[str]:
    if not os.path.exists(dir):
        return None
    return [entry.name for entry in os.scandir(dir) if entry.is_dir()]


def collect_files(install_dir: str) -> Tuple[List[str], List[str]]:
    """
  Return the subdirectories and files of `install_dir`
  """
    partial_dirs = list_directories(install_dir)
    contents = []
    for dir in partial_dirs:
        absolute_dir = f"{install_dir}/{dir}"
        # ogni dir va creata, e quello che c'e' dentro come fonte di un link simbolico

        click.echo(f"📂 Found Directory: {dir}")
        # Lista file

        # scandir torna solo i file dal parametro in poi.
        for entry in os.scandir(absolute_dir):
            if entry.is_file() or entry.is_dir():
                contents.append(f"{dir}/{entry.name}")

    return (partial_dirs, contents)
