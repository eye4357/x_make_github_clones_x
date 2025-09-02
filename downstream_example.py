import sys
sys.path.insert(0, r"C:\Users\eye43\AppData\Local\Programs\Python\Python313\Lib\site-packages")
from x_make_github_clones_x.x_cls_make_github_clones_x import x_cls_make_github_clones_x

repos_to_clone = [
    "x_0_make_all_x",
    "x_legatus_tactica_core_x",
    "x_make_github_clones_x",
    "x_make_markdown_x",
    "x_make_pip_updates_x",
    "x_make_pypi_x"
]
cloner = x_cls_make_github_clones_x(
    username="eye4357",
    target_dir=r"C:\x_cloned_repos_x",
    yes=True,
    names=",".join(repos_to_clone)
)
cloner.run()
##$env:GITHUB_TOKEN = Read-Host "Enter your GitHub token"