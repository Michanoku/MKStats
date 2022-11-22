# MKStats
Mario Kart 8 Statistics Database

## Notice:
I am still a beginner when it comes to programming and github. I welcome constructive criticism, but please be aware that there are just a lot of things I simply do not know yet. If your question would be: Why didn't you ~ ?, then the answer is probably that I didn't know about it at the time. I'm eager to learn, so please do recommend me things to look into or ways to improve. Thank you. 

## What MKStats does:
This flask web application enables the user to create a racing group of 1-4 people and enter race results for any course currently featured in Mario Kart 8. The user will then be able to see various statistics for that group. 

## Current and planned features:

### Group Creation
- Create a group for 1-4 people
- Name the group
- Name the members
- Upload a personal avatar (optional)

### Group editing 
- Edit the name of the group
- Edit the name of the members
- Upload another avatar
- (PLANNED) Delete the current avatar and revert back to default

### Enter results
- Enter placement for each racer
- Enter date of race
- Select course from list 

### Statistics
- Statistics for each racer about placements and group placements (Actual place achieved in race and placement within the group)
- Statistics for the group, showing the current ranking within the group and the number of points for each racer
- Statistics for each course, how often it was raced and who won most often
- Statistics for each date, how many races and what the results were
- List of data entries where entries can be deleted

### Logout
- The group can log out and another group can log in


## Planned for future development:
- Optimize the python code. There is at least one part that can be made into a function in order to avoid duplication. (The part that handles uploading and resizing avatars)
- Add all non copyrighted material for necessary pictures. I'm not 100% sure what material could be used from the actual game, considering this is not a project for money, but as long as I am not sure, I would like to stay on the safe side. 
- If web deployment would ever be considered, login complete with passwords would need to be implemented. Currently, groups login from a list, as it was developed mostly for personal use.
