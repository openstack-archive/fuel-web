<!-- begin Convert Experiments code--><script type="text/javascript">var _conv_host = (("https:" == document.location.protocol) ? "https://d9jmv9u00p0mv.cloudfront.net" : "http://cdn-1.convertexperiments.com");document.write(unescape("%3Cscript src='" + _conv_host + "/js/10012224-10012014.js' type='text/javascript'%3E%3C/script%3E"));</script><!-- end Convert Experiments code -->

$(document).ready(function(){
	var url = window.location.pathname;
	var filename = url.substring(url.lastIndexOf('/')+1);

	if(filename == 'index.html' || filename == '') {
		$('ul.nav.navbar-nav li.dropdown').not('.globaltoc-container').hide();
	}

	// browser window scroll (in pixels) after which the "back to top" link is shown
	var offset = 300,
	scroll_top_duration = 700,
	//grab the "back to top" link
	$back_to_top = $('.cd-top');

	//hide or show the "back to top" link
	$(window).scroll(function(){
		( $(this).scrollTop() > offset ) ? $back_to_top.addClass('cd-is-visible') : $back_to_top.removeClass('cd-is-visible');
	});

	//smooth scroll to top
	$back_to_top.on('click', function(event){
		event.preventDefault();
		$('body,html').animate({
			scrollTop: 0 ,
		 	}, scroll_top_duration
		);
	});
});