# Documentation on important points.

## Dockerfile updates.

```
current build states: built, unbuilt

shortcodes for convenience:
  dcode = dockerfile_code
  cbuild = current_build
  
Cases creating branches:
  1. dcode is unchanged.
  2. cbuild is unbuilt.
  3. new image id is same.
  4. new image id is different.

Algorithm:

  if dcode is same
    ret

  if cbuild is unbuilt
    update cbuild.dcode
    ret

  Try building new image

  If image ids same
    update cbuild.dcode
    ret
  Else
    replicate build record
    assign new image id to it
    assign dcode to it

    deprecate cbuild
    update image references to point to new build

```
