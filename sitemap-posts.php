<?php
/**
 * Dynamic blog sitemap — fetches posts from Cloudflare Worker.
 * Google reads this automatically via sitemap.xml index.
 */
header('Content-Type: application/xml; charset=utf-8');
header('Cache-Control: public, max-age=3600');

$workerUrl = getenv('WORKER_URL') ?: 'https://portfolio-contact-form.cayz696.workers.dev';
$domain = 'https://www.okdev.win';

function esc($s) {
    return htmlspecialchars($s, ENT_XML1 | ENT_QUOTES, 'UTF-8');
}

function fetch_posts($workerUrl, $lang) {
    $all = [];
    $offset = 0;
    $limit = 50;
    do {
        $url = rtrim($workerUrl, '/') . '/posts?lang=' . urlencode($lang) . '&limit=' . $limit . '&offset=' . $offset;
        $ctx = stream_context_create(['http' => ['timeout' => 15, 'ignore_errors' => true]]);
        $raw = @file_get_contents($url, false, $ctx);
        if (!$raw) break;
        $data = json_decode($raw, true);
        $batch = (is_array($data) && !empty($data['posts'])) ? $data['posts'] : [];
        $all = array_merge($all, $batch);
        $hasMore = !empty($data['hasMore']);
        $offset += $limit;
    } while ($hasMore && $offset < 500);
    return $all;
}

$posts = array_merge(fetch_posts($workerUrl, 'uk'), fetch_posts($workerUrl, 'en'));

echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";

foreach ($posts as $p) {
    $slug = $p['slug'] ?? ($p['id'] ?? '');
    if (!$slug) continue;
    $lang = ($p['lang'] ?? 'uk') === 'en' ? 'en' : 'uk';
    $loc = $domain . ($lang === 'en' ? '/en/blog/' : '/blog/') . rawurlencode($slug) . '/';
    $lastmod = isset($p['publishedAt']) ? substr($p['publishedAt'], 0, 10) : date('Y-m-d');
    echo "  <url>\n";
    echo '    <loc>' . esc($loc) . "</loc>\n";
    echo '    <lastmod>' . esc($lastmod) . "</lastmod>\n";
    echo "    <changefreq>monthly</changefreq>\n";
    echo "    <priority>0.6</priority>\n";
    echo "  </url>\n";
}

echo "</urlset>\n";
