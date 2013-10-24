### Change log:

#### Version 1.9.12
+ Fixed brackets on page load when the decimal character is a comma.

#### Version 1.9.11
+ Another mod to the 'set' method.

#### Version 1.9.10
+ Fixed the 'set' method to handle page reload using the back button.

#### Version 1.9.9
+ Fixed how non-input tags default value is handled.  When the default is an empty string and aSign is not empty the return value is now and empty string.
+ Modified how default values are handled when the decimal character equals ',' comma. Your default value can now use either a a period '.' or comma ',' as the decimal separator
+ Modified the caret placement on focusin (tab in). If only the currency sign is visible the caret is placed in the proper location depending on the sign placement (prefix or suffix).  

#### Version 1.9.8
+ Changed bind / unbind to on / off.
+ added lastSetValue to settings - this saves the unrounded value from the set method - $('selector').data('autoNumeric').lastSetValue; - helpful when you need to change the rounding accuracy

#### Version 1.9.7
+ Modified /fixed the format default values on page ready.
+ Fixed the caret position when jumping over the thousand separator with back arrow.

#### Version 1.9.6
+ Fixed bug introduced in 1.9.3 with shift key.
+ additional modification to the processKeypress function that automatically inserts a negative sign when vMax less tham or equal to 0 and vMin is less tham vMax.

#### Version 1.9.5
+ Modified processKeypress function to automatically insert a negative sign when vMax <=0 and vMin < 0.
+ Changed the getSting and getArray functions to use decodeURIComponent() instead of unescape() which is depreciated

#### Version 1.9.4
+ Merged issue #11 - Both getString and getArray were using escaped versions of the name from jQuery's serialization. So this change wraps the name finder with quotes and unescapes the name.Fixed a bug in autoCode that corrects the pasted values and page re-load - Thanks Cory.
+ Merged issue #12 - If a input is readonly during "init", autocomplete won't work if the input is enabled later. This commit should fix the Problem - Thanks Sven.

#### Version 1.9.3

+ Fixed a bug in autoCode function that corrects pasted values and page re-load
+ Added support for "shift" + "insert" paste key combination

#### Version 1.9.2

+ Modified the "checkValue" function - eliminated redundant code
+ Modified the "update" method include calling the "getHolder" function which updates the regular expressions
+ Modified the "getHolder function so the regular expressions are updated
+ Modified the "set" method to convert value from number to string

#### Version 1.9.1

+ Modified the checkValue function to handle values as text with the exception of values less than "0.000001 and greater than -1"

#### Version 1.9.0

+ Fixed a rounding error when the integers were 15 or more digits in length
+ Added "use strict";

#### version 1.8.9

+ Fixed the "get" and "set" methods by moving the settings.oEvent property to ensure the error message would be thrown if the element had not been inialized prior to calling the "get" and "set" methods

#### Version 1.8.8

+ Fixed the "init" when there is a default and value aForm=true and the aSep and aDec are not the defaults

#### Version 1.8.7

+ Fixed the "getSting" method - it use to returned an error when no values were entered 
+ Modified the "init" method to better handle default and pre-existing values
+ Modified the "set" method - removed the routine that checked for values less than .000001 and greater than -1 and placed it in a separate function named checkValue()
+ Modified the "get" method:
	+ Added a call to the checkValue() function - this corrects returned values example - when the input value was "12." the returned value was "12." - it now returns "12" 
	+ When no numeric character is entered the returned value is an empty string "". 

#### Version 1.8.6

+ Removed the error message when calling the 'init' methods multiple times. This was done when using the class selector for the 'init' method and then dynamically adding input(s) it allows you to use the same selector to init autoNumeric. **Please note:** if the input is already been initialized no changes to the option will occur you still need to use the update method to change exisiting options.
+ Added support for brackets '[,]', parentheses '(,)', braces '{,}' and '<,>' to the nBracket setting. **Please note:** the following format nBracket: '(,)' that the left and right symbol used to represent negative numbers must be enclosed in quote marks and separated by a comma to function properly. 

#### Version 1.8.5

+ Fixed readonly - this occured when you toggle the readonly attribute


#### Version 1.8.4

+ Fixed the getString and getArray methods under jQuery-1.9.1


#### version on 1.8.3

+ Added input[type=hidden] support - this was done mainly for backward compatibility.

+ The "get" method now returns a numeric string - this also was done for backward compatibility.


#### Version 1.8.2

+ Allowed dGroup settings to be passed as a numeric value or text representing a numeric value

+ Allows input fields without type that defaults to type text - Thanks Mathieu DEMONT


#### Version 1.8.1

+ Modified the 'get' method so when a field is blank and the setting wEmpty:'empty' a empty string('') is returned.


#### Version 1.8.0

+ autoNumeric() 1.8.0 is not compatible with earlier versions but I believe you will find version 1.8.0's new functionality and ease of use worth the effort to convert.

+ Changed autoNumeric structure to conform to jQuery's recommended plugin development. 

+ Created a single namespace and added multiple methods.

+ Added HTML 5 data support and eliminated the metadata plugin dependency. 

+ Added support for the following elements: 'DD', 'DT', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'input', 'LABEL', 'P', 'SPAN', 'TD', 'TH'.

+ Changed the settings loading order to defaults, HTML5 data then options. Now the defaults settings are overridden by HTML5 data and options overrides both defaults & HTML5 data.

+ Added "lZero" to the settings to control leading zero behavior.

+ Added "nBracket" to the settings which controls if negative values are display with brackets.

+ Changed the callback feature to accept functions only.

+ Improved the 'aForm' behavior that allows values to be automatically formatted on page ready.

+ Fixed the issue for numbers that are less than 1 and greater than -1 and have six or more decimal places.

+ Fixed 'crtl' + 'a' (select all) and 'ctrl' + 'c' (copy) combined key events.

+ Fixed a IE & FF bug on readonly attribute.

+ General code clean up