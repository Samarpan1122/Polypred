import re

with open("backend/app/services/training_service.py", "r") as f:
    code = f.read()

new_eval_block = """    # Evaluate
    model.eval()
    preds = []
    
    test_loader = DataLoader(PairDataset(te_df, list(range(len(te_df)))), batch_size=bs, collate_fn=my_collate_fn)
    
    with torch.no_grad():
        for batch_a, batch_b, _ in test_loader:
            try:
                batch_a = batch_a.to(device)
                batch_b = batch_b.to(device)
                p = model(batch_a, batch_b).cpu().numpy()
                preds.append(p)
            except Exception:
                pass"""

# Match old eval block manually
code = re.sub(
    r"    # Evaluate\n    model\.eval\(\)\n    preds = \[\]\n    with torch\.no_grad\(\):\n        try:\n            from torch_geometric\.data import Batch\n            for start in range\(0, len\(graphs_a_te\), bs\):\n                ga_b = \[graph_dict_to_single_pyg\(graphs_a_te\[i\], device\) for i in range\(start, min\(start \+ bs, len\(graphs_a_te\)\)\)\]\n                gb_b = \[graph_dict_to_single_pyg\(graphs_b_te\[i\], device\) for i in range\(start, min\(start \+ bs, len\(graphs_b_te\)\)\)\]\n                ba = Batch\.from_data_list\(ga_b\)\n                bb = Batch\.from_data_list\(gb_b\)\n                p = model\(ba, bb\)\.cpu\(\)\.numpy\(\)\n                preds\.append\(p\)\n        except Exception:\n            pass",
    new_eval_block,
    code
)

with open("backend/app/services/training_service.py", "w") as f:
    f.write(code)
