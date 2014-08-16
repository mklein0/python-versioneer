
def git_get_vcs_root(root):
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

def git_versions_from_vcs(tag_prefix, root, verbose=False):
    # this runs 'git' from the root of the source tree. This only gets called
    # if the git-archive 'subst' keywords were *not* expanded, and
    # _version.py hasn't already been rewritten with a short version string,
    # meaning we're inside a checked out source tree.

    if not os.path.exists(os.path.join(root, ".git")):
        if verbose:
            print("no .git in %s" % root)
        return {}

    GITS = ["git"]
    if sys.platform == "win32":
        GITS = ["git.cmd", "git.exe"]
    cmdline = ["describe", "--tags", "--dirty", "--always"]
    if tag_prefix:
        cmdline.extend(("--match", tag_prefix + "*"))
    stdout = run_command(GITS, cmdline, cwd=root)
    if stdout is None:
        return {}
    if not stdout.startswith(tag_prefix):
        if verbose:
            print("tag '%s' doesn't start with prefix '%s'" % (stdout, tag_prefix))
        return {}
    tag = stdout[len(tag_prefix):]
    stdout = run_command(GITS, ["rev-parse", "HEAD"], cwd=root)
    if stdout is None:
        return {}
    full = stdout.strip()
    if tag.endswith("-dirty"):
        full += "-dirty"
    tag = vcs_tag_transform(tag, root)
    return {"version": tag, "full": full}

def vcs_alter_time(vcs_root):
    # Determine most recent change time of modified track files.
    #
    GITS = ["git"]
    if sys.platform == "win32":
        GITS = ["git.cmd", "git.exe"]
    stdout = run_command(GITS, ["diff-index", "--name-status", "HEAD"],
                         cwd=vcs_root)

    ctime = 0.0
    for line in stdout.split("\n"):
        if "d" != line[0].lower():
            filepath = line[2:]
            stats = os.stat(os.path.join(vcs_root, filepath))
            ctime = max(ctime, stats.st_ctime, stats.st_mtime)

    return datetime.datetime.fromtimestamp(ctime)

_RELATIVE_COMMIT = re.compile(r'-(\d+)-g[0-9a-fA-F]+$')

def vcs_tag_transform(vcs_tag, vcs_root):
    # Convert git describe tag to a pypi safe version id.
    post_tag = ""
    dev_tag = ""

    # Transform dirty bit
    if vcs_tag.endswith("-dirty"):
        # Timestamp for dev labels
        atime = vcs_alter_time(vcs_root)
        dev_tag = atime.strftime(".dev%Y%m%d%H%M%S")
        vcs_tag = vcs_tag[:-6]

    # Transform relative commit
    search = _RELATIVE_COMMIT.search(vcs_tag)
    if search:
        post_tag = ".post%s" % search.group(1)
        vcs_tag = vcs_tag.rsplit("-", 2)[0]

    return "%s%s%s" % (vcs_tag, post_tag, dev_tag)
