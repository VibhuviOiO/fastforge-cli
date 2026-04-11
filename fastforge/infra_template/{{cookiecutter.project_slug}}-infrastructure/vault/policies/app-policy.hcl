path "secret/data/{{ cookiecutter.project_slug }}/*" {
  capabilities = ["read", "list"]
}

path "secret/metadata/{{ cookiecutter.project_slug }}/*" {
  capabilities = ["list"]
}
