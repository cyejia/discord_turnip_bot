// Pulls prices of DIY furniture from https://animalcrossing.fandom.com/wiki/Furniture_(New_Horizons)

let tables = $("#mw-content-text table.article-table")

// tables[1].tBodies[0].children[1].children[4].textContent

let furniture = {}
for (let i = 0; i < tables.length; i++) {
  for (let row of tables[i].tBodies[0].children) {
      if (row.children[0].nodeName == "TD") {
          if (row.children[4].textContent.trim() == "DIY Recipes") {
              // col 0 is furniture name
              // col 3 is sell cost
              furniture[row.children[0].textContent.trim()] = row.children[3].textContent.trim()

          }

      }

  }
}

JSON.stringify(furniture)