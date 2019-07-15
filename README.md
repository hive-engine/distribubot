# distribubot

### Distribute by manual command through comments
Scans blocks for new comments containing the given comment_command. The the comment author has suffient
 token, the token account will send token to the parent author.


#### Running
Can be running all day, will only be active when a comment with the comment_command was broadcasted.
More than one token_account and  token can be specified. Please check config.json.example.

```
$ distribubot /path/to/config.json
```

|        Option       | Value                                                |
|:-------------------:|------------------------------------------------------|
| token_account | steem account name, which should distribute the token       |
| symbol   | token symbol, which should be distributed                   |
| token_memo   | memo which is attached to each token transfer               |
| reply        | when true, a reply comment is broadcasted                   |
| wallet_password | Contains the beempy wallet password |
| no_broadcast | When true, no transfer is made |
| min_staked_token | Minimum amount of token a comment writer must have |
| maximum_amount_per_comment | Maximum Amount of token that will be send at once|
| token_in_wallet_for_each_outgoing_token | Limits the amount of token a user can send every 24 hours |
| user_can_specify_amount | When true, the user can specify the amount to send up to maximum_amount, when false maximum_amount is always sent |
| sucess_reply_body | Reply body, when token are send|
| no_token_left_for_today | Reply body, when the user has not sufficient token in its wallet |
| fail_reply_body | Reply body, when no token are sent (not min_staked_token available) |
| no_token_left_body | Reply body, when no token are left to send |
| comment_command | Command which must be included in a comment, to activate the bot |
| usage_upvote_percentage | When set to a percentage higher than 0, the comment with the command will be upvoted by the scot_account |