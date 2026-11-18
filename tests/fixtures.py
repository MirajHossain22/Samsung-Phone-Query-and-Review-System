# Minimal HTML that mimics the GSMArena markup the scraper relies on (h1.specs-phone-name-title,
# #specs-list tables with <th> category, td.ttl / td.nfo rows, empty td.ttl for continuation rows).
PHONE_HTML = """
<html><body>
<h1 class="specs-phone-name-title" data-spec="modelname">Samsung Galaxy S23</h1>
<div class="specs-photo-main"><a href="#"><img src="https://fdn2.gsmarena.com/vv/bigpic/s23.jpg"></a></div>
<div id="specs-list">
<table cellspacing="0"><tbody>
 <tr><th rowspan="2" scope="row">Launch</th><td class="ttl"><a href="#">Announced</a></td><td class="nfo" data-spec="released-hl">2023, February 01</td></tr>
</tbody></table>
<table cellspacing="0"><tbody>
 <tr><th rowspan="3" scope="row">Display</th><td class="ttl"><a href="#">Type</a></td><td class="nfo">Dynamic AMOLED 2X, 120Hz, HDR10+</td></tr>
 <tr><td class="ttl"><a href="#">Size</a></td><td class="nfo">6.1 inches, 146.7 cm2</td></tr>
 <tr><td class="ttl"><a href="#">Resolution</a></td><td class="nfo">1080 x 2340 pixels, 19.5:9 ratio</td></tr>
</tbody></table>
<table cellspacing="0"><tbody>
 <tr><th rowspan="2" scope="row">Memory</th><td class="ttl"><a href="#">Internal</a></td><td class="nfo">128GB 8GB RAM, 256GB 8GB RAM, 512GB 8GB RAM</td></tr>
 <tr><td class="ttl">&nbsp;</td><td class="nfo">UFS 3.1 (128GB), UFS 4.0</td></tr>
</tbody></table>
<table cellspacing="0"><tbody>
 <tr><th rowspan="2" scope="row">Main Camera</th><td class="ttl"><a href="#">Triple</a></td><td class="nfo">50 MP, f/1.8, 24mm (wide)<br>10 MP, f/2.4 (telephoto)<br>12 MP, f/2.2 (ultrawide)</td></tr>
 <tr><td class="ttl"><a href="#">Video</a></td><td class="nfo">8K@24/30fps</td></tr>
</tbody></table>
<table cellspacing="0"><tbody>
 <tr><th rowspan="2" scope="row">Battery</th><td class="ttl"><a href="#">Type</a></td><td class="nfo">Li-Ion 3900 mAh</td></tr>
 <tr><td class="ttl"><a href="#">Charging</a></td><td class="nfo">25W wired, PD3.0, 50% in 30 min<br>15W wireless</td></tr>
</tbody></table>
<table cellspacing="0"><tbody>
 <tr><th rowspan="1" scope="row">Misc</th><td class="ttl"><a href="#">Price</a></td><td class="nfo">$ 799.99 / € 859.00 / £ 699.00</td></tr>
</tbody></table>
</div></body></html>
"""

LISTING_HTML = """
<div class="makers"><ul>
<li><a href="samsung_galaxy_s23-12082.php"><img src="x.jpg"><strong><span>Galaxy S23</span></strong></a></li>
<li><a href="samsung_galaxy_s23_ultra-12024.php"><img src="y.jpg"><strong><span>Galaxy S23 Ultra</span></strong></a></li>
</ul></div>
<div class="nav-pages"><a class="pages-next" href="samsung-phones-f-9-0-p2.php">&#8250;</a></div>
"""
