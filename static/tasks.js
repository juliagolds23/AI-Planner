document.addEventListener('DOMContentLoaded', function() {
    let checkboxes = document.querySelectorAll('.checkbox');
    // Loop through each checked row
    for (let i = 0; i < checkboxes.length; i++) {
        // listen for change in checkbox
        checkboxes[i].addEventListener('change', function() {
             
            // Create a new AJAX request
            let xhr = new XMLHttpRequest();
            xhr.open('POST', '/checkbox'); 
            xhr.setRequestHeader('Content-Type', 'application/json');
            const isChecked = checkboxes[i].checked ? 1 : 0
            xhr.send(JSON.stringify({
                'task_id': checkboxes[i].id,
                'status': isChecked
            }));
        });
    }
});