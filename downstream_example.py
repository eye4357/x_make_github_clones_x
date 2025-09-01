"""Tiny example showing how a downstream process can invoke x_cls_clone_all_x.

This example imports the cloner, constructs it with desired options, runs it,
and consumes the returned timestamped folder path. This is a minimal demo
and not a full test harness.
"""

from x_cls_clone_all_x import x_cls_clone_all_x



def main():
    # Create a cloner instance and explicitly specify the destination folder
    target_dir = r"C:\x_cloned_repos_x"
    # Example whitelist (comma-separated repo names to include)
    whitelist = ",".join([
        "x_0_make_all_x",
        "x_make_github_clones_x",
        "x_make_markdown_x",
        "x_make_pip_updates_x",
        "x_make_pypi_x",
        "x_legatus_tactica_core_x"
    ])
    print("Using whitelist:", whitelist)
    cloner = x_cls_clone_all_x(username="eye4357", target_dir=target_dir, yes=True, names=whitelist)

    # Run the cloner and get the target folder path
    try:
        dest = cloner.run()
    except AssertionError as e:
        print("Cloner reported failures:", e)
        raise

    if dest:
        print("Repositories are synchronized in:", dest)
    else:
        print("Cloner did not produce a destination folder; check logs.")


if __name__ == '__main__':
    main()
##$env:GITHUB_TOKEN = Read-Host "Enter your GitHub token"