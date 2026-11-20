# Rahul K. Gupta, Ph.D. — research website

Built on the [al-folio](https://github.com/alshedivat/al-folio) Jekyll template (MIT licence). Pages:
About · Publications · Research · CV · Collaborations · People · Extracurricular.

## Where content lives

| Page            | Edit                                                                 |
| :-------------- | :------------------------------------------------------------------- |
| About           | `_pages/about.md`, photo `assets/img/prof_pic.jpg`                   |
| Publications    | `_bibliography/papers.bib` (BibTeX)                                  |
| Research        | one file per topic in `_projects/` (`category: current` or `completed`) |
| CV              | `_data/cv.yml`; PDF at `assets/pdf/cv.pdf`                           |
| Collaborations  | `_pages/collaborations.md` (Markdown table)                          |
| People          | `_pages/profiles.md` (one block per member) + `_pages/profile_*.md`  |
| Extracurricular | `_pages/extracurricular.md`, photos in `assets/img/extracurricular/` |
| News            | one file per item in `_news/`                                        |
| Social links    | `_data/socials.yml`                                                  |

## Items still to complete

1. Replace `assets/img/prof_pic.jpg` with your photo (keep the filename); the current file is the template placeholder.
2. Replace `assets/pdf/cv.pdf` with your CV.
3. Replace `_bibliography/papers.bib` with a Google Scholar export
   (profile → select all → Export → BibTeX); two entries currently carry an incomplete author list.
4. Confirm the position title and start date in `_data/cv.yml` and `_pages/about.md`.
5. Add group members in `_pages/profiles.md`, or delete the template block.
6. Set `url:` in `_config.yml` to your domain once registered.

## Deploy on GitHub Pages

1. Create a public GitHub repository (e.g. `rahulkgupta-site`) and push this folder:
   ```bash
   git remote add origin https://github.com/<username>/<repo>.git
   git push -u origin main
   ```
2. Repository → Settings → Actions → General → Workflow permissions → **Read and write**.
3. The **Deploy site** workflow builds the site on every push and publishes it to the `gh-pages` branch.
4. Settings → Pages → Source: **Deploy from a branch**, branch `gh-pages`, folder `/ (root)`.

## Custom domain

1. Register the domain with any registrar (e.g. Cloudflare Registrar, Namecheap, Porkbun).
2. Create a file named `CNAME` in the repository root containing only the domain, e.g. `rahulkgupta.com`.
3. At the registrar, add DNS records:
   - apex (`@`): four `A` records → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www`: `CNAME` → `<username>.github.io`
4. Set `url: https://rahulkgupta.com` in `_config.yml` (leave `baseurl` blank) and push.
5. Settings → Pages → Custom domain: enter the domain, wait for the DNS check, then tick **Enforce HTTPS**.

## Local preview (optional)

```bash
bundle install
bundle exec jekyll serve   # http://localhost:4000
```

