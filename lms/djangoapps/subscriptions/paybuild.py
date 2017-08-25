#
# build cb payment
#
def build_cb_payment(typesus, studentid, studentemail, debug_mode='0'):
	import uuid
	
	sustype = "Free"
	sysmodel = "For Individuals"
	amount = 0
	
	if typesus == '1' or typesus == '4':
		if typesus == '4':
			susmodel = "For Enterprise"
	elif typesus == '2' or typesus == '3':
		if typesus == '2':
			sustype = "Basic"
			amount = 99.00
		else:
			sustype = "Plus"
			amount = 199.00
	elif typesus == '5' or typesus == '6':
		susmodel = "For Enterprise"
		if typesus == '5':
			sustype = "Plus"
			amount = 199.00
		else:
			sustype = "Pro"
			amount = 499.00

	# amount Format EUR (####.##)
	if amount > 0:
		amount = str(amount)
		amount = amount.replace(',', '.')
		amount = float(amount)
		# amount = "{0:0.2f}".format(amount)
	else:
		amount = 0

    #
	# Params and return form
	#
	#url_pay = 'https://www.sandbox.paypal.com/cgi-bin/webscr'  # url payment develop
	#merchan_id = "calzada-facilitator@iblstudios.com"  # merchan_id or merchan_email
	url_pay='https://www.paypal.com/cgi-bin/webscr' #url payment production
	merchan_id = "sales@buildacademy.com"  # merchan_id or merchan_email
	
	item_name = "Subscription %s %s" % (sysmodel, sustype)
	item_number = uuid.uuid4().hex  # uniqueid
	currency_code = "USD"
	locale_code = "en_US"
	btn_txt = 'Pay with PayPal'
	notify_url = "https://courses.buildacademy.com/paysubscallback"  # post process
	return_url = "https://courses.buildacademy.com/subscription?m=%s&pay=done" % (typesus) # back url user
	custom = '%s|%s' % (studentid, typesus)


    # construct dict
	import collections
	
	arr_data_to_send = collections.OrderedDict()
	arr_data_to_send.update({ 'business' : merchan_id })
	arr_data_to_send.update({ 'cmd' : '_ext-enter' })
	arr_data_to_send.update({ 'redirect_cmd' : '_xclick-subscriptions' })
	arr_data_to_send.update({ 'display' : '0' })
	arr_data_to_send.update({ 'no_shipping' : '1' })
	arr_data_to_send.update({ 'item_name' : item_name })
	arr_data_to_send.update({ 'item_number' : item_number })
	arr_data_to_send.update({ 'quantity' : '1' })
	arr_data_to_send.update({ 'amount' : amount })
	arr_data_to_send.update({ 'currency_code' : currency_code })
	arr_data_to_send.update({ 'lc' : locale_code })
	#arr_data_to_send.update({ 'login_email' : studentemail })
	arr_data_to_send.update({ 'email' : studentemail })
	arr_data_to_send.update({ 'user_id' : studentid })
	arr_data_to_send.update({ 'type_sus' : typesus })
	arr_data_to_send.update({ 'no_note' : 1 })
	arr_data_to_send.update({ 'custom' : custom })
    # control payment
	arr_data_to_send.update({ 'notify_url' : notify_url })
	arr_data_to_send.update({ 'rm' : 2 })
	arr_data_to_send.update({ 'cbt' : 'Back To Build Academy' })
	arr_data_to_send.update({ 'return' : return_url })
	arr_data_to_send.update({'a3': amount})
	arr_data_to_send.update({'t3': 'Y'})
	arr_data_to_send.update({'p3': '1'})
	arr_data_to_send.update({'src': '1'})

	# create form
	if debug_mode != '0':
		result = '<form action="%s" name="payment_submit" id="payment_submit" method="post">' % (url_pay)
		for (k, v) in arr_data_to_send.items():
			result += '<input type="text" name="%s" value="%s">' % (k, v)
		result += '<br><span class="submitbutton"><i class="fa fa-paypal"></i> %s</span>' % (btn_txt)
		result += "</form>"
	else:
		result = '<form action="%s" name="payment_submit" id="payment_submit" method="post">' % (url_pay)
		for (k, v) in arr_data_to_send.items():
			result += '<input type="hidden" name="%s" value="%s">' % (k, v)
		result += '<button type="submit" class="submitbutton"><i class="fa fa-paypal"></i> %s</button>' % (btn_txt)
		result += "</form>"
	
	return result
