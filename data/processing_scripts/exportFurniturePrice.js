// Pulls from https://animalcrossing.fandom.com/wiki/DIY_recipes

let tables = $("#mw-content-text table.article-table")

let extractMaterial = (parentElement) => {
	/*
		Example parentElement with craft data:
		<parentElement>
			5x
			<a class="image ..." title="Stone">     // this element is optional
				<img></img>
			</a>
			<a href="..." title="Stone">Stone</a>

			...
			other stuff
			this might be <p>s that nest this. nested parentElements don't have stuff here
			...
		</parentElement>
	*/
	let number = parentElement.firstChild.textContent.trim().toLowerCase().replace('x', '')
	let name = parentElement.querySelector("a:not(.image)").textContent.trim().toLowerCase()
	return {
		"number": number,
		"name": name
	}
}

let extractMaterials = (tdElement) => {
	// tdElement may be empty if there is no craft data
	if (tdElement.textContent.trim().toLowerCase() == "") {
		return null
	}

	// contains craft data
	let materials = [extractMaterial(tdElement)];
	let childParagraphs = tdElement.querySelectorAll("p")
	for (let para of childParagraphs) {
		materials.push(extractMaterial(para))
	}
	return materials
}

let furniture = {}
for (let i = 0; i < tables.length; i++) {
  for (let row of tables[i].tBodies[0].children) {
      if (row.children[0].nodeName != "TD") { // tables should have no th elements
      	debugger;
      }

	  // col 0 is furniture name
	  // col 2 is craft
	  // col 5 is sell price
      let name = row.children[0].textContent.trim().toLowerCase()
      let materials = extractMaterials(row.children[2]);
      let sellPrice = row.children[5].textContent.trim().toLowerCase().replace(' bells', '').replace(',', '')
      furniture[name] = {
      	"materials": materials,
      	"sell": sellPrice ? sellPrice : null
      }
  }
}

JSON.stringify(furniture)