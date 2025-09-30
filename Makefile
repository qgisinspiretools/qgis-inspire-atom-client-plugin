COMPILED_RESOURCE_FILES = resources.py

UI_FILES = ui_metadataclient.py ui_inspireatomclient.py


default: compile

compile: $(COMPILED_RESOURCE_FILES) $(UI_FILES)

%.py : %.ui
	pyuic4 -o $@ $<

%.py : %.qrc
	pyrcc4 -o $*.py  $<



pb_deploy:
	@echo "------------------------------------"
	@echo "Deploying plugin with pb_tool..."
	@echo "------------------------------------"
	pb_tool deploy

pb_zip:
	@echo "------------------------------------"
	@echo "Creating plugin ZIP with pb_tool..."
	@echo "------------------------------------"
	pb_tool zip

pb_clean:
	@echo "------------------------------------"
	@echo "Removing deployed plugin..."
	@echo "------------------------------------"
	pb_tool clean