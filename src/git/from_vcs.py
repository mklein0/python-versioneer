import os, sys, re # --STRIP DURING BUILD
def register_vcs_handler(*args): # --STRIP DURING BUILD
    def nil(f): # --STRIP DURING BUILD
        return f # --STRIP DURING BUILD
    return nil # --STRIP DURING BUILD
def run_command(): pass # --STRIP DURING BUILD
class NotThisMethod(Exception): pass  # --STRIP DURING BUILD

@register_vcs_handler("git", "pieces_from_vcs")
def git_pieces_from_vcs(cfg, root, verbose, run_command=run_command):
    """Get version from 'git describe' in the root of the source tree.

    This only gets called if the git-archive 'subst' keywords were *not*
    expanded, and _version.py hasn't already been rewritten with a short
    version string, meaning we're inside a checked out source tree.
    """
    vcs_root = git_get_vcs_root(root)
    if not os.path.exists(os.path.join(vcs_root, ".git")):
        if verbose:
            print("no .git in %s" % vcs_root)
        raise NotThisMethod("no .git directory")

    if cfg.tagfile_source:
        return git_pieces_from_tagfile(cfg.tagfile_source, root, vcs_root,
                                       verbose, run_command)
    else:
        return git_pieces_from_describe(cfg.tag_prefix, vcs_root, verbose,
                                        run_command)

def git_pieces_from_describe(tag_prefix, vcs_root, verbose, run_command):

    GITS = ["git"]
    if sys.platform == "win32":
        GITS = ["git.cmd", "git.exe"]
    # if there is a tag matching tag_prefix, this yields TAG-NUM-gHEX[-dirty]
    # if there isn't one, this yields HEX[-dirty] (no NUM)
    describe_out = run_command(GITS, ["describe", "--tags", "--dirty",
                                      "--always", "--long",
                                      "--match", "%s*" % tag_prefix],
                               cwd=vcs_root)
    # --long was added in git-1.5.5
    if describe_out is None:
        raise NotThisMethod("'git describe' failed")
    describe_out = describe_out.strip()
    full_out = run_command(GITS, ["rev-parse", "HEAD"], cwd=vcs_root)
    if full_out is None:
        raise NotThisMethod("'git rev-parse' failed")
    full_out = full_out.strip()

    pieces = {}
    pieces["long"] = full_out
    pieces["short"] = full_out[:7]  # maybe improved later
    pieces["error"] = None

    # parse describe_out. It will be like TAG-NUM-gHEX[-dirty] or HEX[-dirty]
    # TAG might have hyphens.
    git_describe = describe_out

    # look for -dirty suffix
    dirty = git_describe.endswith("-dirty")
    pieces["dirty"] = dirty
    if dirty:
        git_describe = git_describe[:git_describe.rindex("-dirty")]

    # now we have TAG-NUM-gHEX or HEX

    if "-" in git_describe:
        # TAG-NUM-gHEX
        mo = re.search(r'^(.+)-(\d+)-g([0-9a-f]+)$', git_describe)
        if not mo:
            # unparseable. Maybe git-describe is misbehaving?
            pieces["error"] = ("unable to parse git-describe output: '%s'"
                               % describe_out)
            return pieces

        # tag
        full_tag = mo.group(1)
        if not full_tag.startswith(tag_prefix):
            if verbose:
                fmt = "tag '%s' doesn't start with prefix '%s'"
                print(fmt % (full_tag, tag_prefix))
            pieces["error"] = ("tag '%s' doesn't start with prefix '%s'"
                               % (full_tag, tag_prefix))
            return pieces
        pieces["closest-tag"] = full_tag[len(tag_prefix):]

        # distance: number of commits since tag
        pieces["distance"] = int(mo.group(2))

        # commit: short hex revision ID
        pieces["short"] = mo.group(3)

    else:
        # HEX: no tags
        pieces["closest-tag"] = None
        count_out = run_command(GITS, ["rev-list", "HEAD", "--count"],
                                cwd=vcs_root)
        pieces["distance"] = int(count_out)  # total number of commits

    return pieces

def git_pieces_from_tagfile(tagfile_source, root, vcs_root, verbose,
                            run_command):

    abs_path = os.path.join(root, tagfile_source)
    if not os.path.exists(abs_path):
        raise NotThisMethod("no tag file present")

    try:
        with open(abs_path, 'r') as fobj:
            label_out = fobj.readline()
    except IOError:
        raise NotThisMethod("unable to read tag file")

    if label_out is None:
        raise NotThisMethod("No tag in tag file")

    label_out = label_out.strip()
    if not label_out:
        raise NotThisMethod("No tag in tag file")

    GITS = ["git"]
    if sys.platform == "win32":
        GITS = ["git.cmd", "git.exe"]
    # Look up latest version of tagfile
    base_version_out = run_command(GITS, ["rev-list", "--max-count=1", "HEAD",
                                          "--", tagfile_source],
                               cwd=root)
    if base_version_out is None:
        raise NotThisMethod("'git rev-list' tag file failed")

    base_version_out = base_version_out.strip()

    tagfile_out = run_command(GITS, ["diff-index", "HEAD", tagfile_source],
                              cwd=root)
    if tagfile_out is None:
        raise NotThisMethod("'git diff-index' tagfile failed")
    tagfile_out = tagfile_out.strip()

    full_out = run_command(GITS, ["log", "--max-count=1",
                                  "--format=format:%H:%h", "HEAD"],
                        cwd=vcs_root)
    if full_out is None:
        raise NotThisMethod("'git log' failed")
    full_out, abbrev_out = full_out.strip().split(':', 1)

    if tagfile_out:
        count_out = 0
        dirty_out = tagfile_out

    else:
        count_out = run_command(GITS, ["rev-list", "--count",
                                       "%s..HEAD" % base_version_out],
                                cwd=vcs_root)
        if count_out is None:
            raise NotThisMethod("'git rev-list' history failed")

        dirty_out = run_command(GITS, ["diff-index", "HEAD"], cwd=vcs_root)
        if dirty_out is None:
            raise NotThisMethod("'git diff-index' failed")
        dirty_out = dirty_out.strip()

    pieces = {
        "long": full_out,
        "short": abbrev_out,
        "error": None,
        "dirty": bool(dirty_out),
        "closest-tag": label_out,
        "distance": int(count_out),
    }
    return pieces

def git_get_vcs_root(root):
    """Determine location of .git directory via "git rev-parse" command.
    """
    # Use command line to look for root of vcs instead
    # of a manual directory traversal.
    GITS = ["git"]
    if sys.platform == "win32":
        GITS = ["git.cmd", "git.exe"]
    stdout = run_command(GITS, ["rev-parse", "--show-toplevel"],
                         cwd=root)
    if not stdout:
        # command line was unable to determine root
        return root
    return stdout
