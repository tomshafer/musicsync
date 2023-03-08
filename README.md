# Synchronize Apple Music to an External Volume

``` bash
$ musicsync --playlist "Selected for Car" /Volumes/UNTITLED

Collecting songs from playlist "Selected for Car"
  Collected 2514 songs
Playlist root directory is "/Users/tomshafer/Music/Music/Media.localized/Music/"
Building playlist song tree
  Found 365 dirs and 2514 files
Removing extra files from "/Volumes/UNTITLED/"
Copying new files from "Selected for Car" to "/Volumes/UNTITLED/"
  Aaron Keyes/In the Living Room:  17%|██          | 2/12 [00:06<00:25,  2.60s/it]
```

## Installation

``` bash
$ git clone git@github.com:tomshafer/musicsync.git
$ pip install ./musicsync
```


## Usage

``` bash
$ musicsync --help
Usage: musicsync [OPTIONS] VOLUME

Options:
  -h, --help           Show this message and exit.
  -v, --verbose        Enable debug logging.
  -p, --playlist NAME  Apple Music playlist to sync.
```
